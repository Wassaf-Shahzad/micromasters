"""
Functions for ecommerce
"""
from base64 import b64encode
import hashlib
import hmac
from itertools import chain
import logging
from urllib.parse import quote_plus
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from edx_api.client import EdxApi

from courses.models import (
    CourseRun,
    Program,
)
from dashboard.api_edx_cache import (
    CachedEdxDataApi,
    CachedEdxUserData,
)
from dashboard.models import ProgramEnrollment
from dashboard.utils import MMTrack, get_mmtrack
from dashboard.api import has_to_pay_for_exam
from ecommerce.exceptions import (
    EcommerceEdxApiException,
    EcommerceException,
    ParseException,
)
from ecommerce.models import (
    Coupon,
    Line,
    Order,
    RedeemedCoupon,
)
from financialaid.api import get_formatted_course_price
from financialaid.models import (
    FinancialAid,
    FinancialAidStatus,
    TierProgram
)
from micromasters.utils import now_in_utc
from profiles.api import get_edxorg_social_auth


ISO_8601_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
log = logging.getLogger(__name__)
_REFERENCE_NUMBER_PREFIX = 'MM-'


def get_purchasable_course_run(course_key, user):
    """
    Gets a course run, or raises Http404 if not purchasable. To be purchasable a course run
    must not already be purchased, must be part of a live program, must be part of a program
    with financial aid enabled, with a financial aid object, and must have a valid price.

    Args:
        course_key (str):
            An edX course key
        user (User):
            The purchaser of the course run
    Returns:
        CourseRun: A course run
    """
    # Make sure it's connected to a live program, it has a valid price, and the user is enrolled in the program already
    try:
        course_run = get_object_or_404(
            CourseRun,
            edx_course_key=course_key,
            course__program__live=True,
            course__program__financial_aid_availability=True,
        )
    except Http404:
        log.warning("Course run %s is not purchasable", course_key)
        raise

    if not FinancialAid.objects.filter(
            tier_program__current=True,
            tier_program__program__course__courserun=course_run,
            user=user,
            status__in=FinancialAidStatus.TERMINAL_STATUSES,
    ).exists():
        log.warning("Course run %s has no attached financial aid for user %s", course_key, user.username)
        raise ValidationError(
            "Course run {} does not have a current attached financial aid application".format(course_key)
        )

    # Make sure it's not already purchased
    if Line.objects.filter(
            order__status__in=Order.FULFILLED_STATUSES,
            order__user=user,
            course_key=course_run.edx_course_key,
    ).exists():
        mmtrack = get_mmtrack(user, course_run.course.program)
        if not has_to_pay_for_exam(mmtrack, course_run.course):
            log.warning("Course run %s is already purchased by user %s", course_key, user)
            raise ValidationError("Course run {} is already purchased".format(course_key))

    return course_run


@transaction.atomic
def create_unfulfilled_order(course_key, user):
    """
    Create a new Order which is not fulfilled for a purchasable course run. If course run is not purchasable,
    it raises an Http404

    Args:
        course_key (str):
            A course key
        user (User):
            The purchaser of the course run
    Returns:
        Order: A newly created Order for the CourseRun with the given course_id
    """
    course_run = get_purchasable_course_run(course_key, user)
    price, coupon = calculate_run_price(course_run, user)
    if price < 0:
        log.error(
            "Price to be charged for course run %s for user %s is less than zero: %s",
            course_key,
            user.username,
            price,
        )
        raise ImproperlyConfigured("Price to be charged is less than zero")

    order = Order.objects.create(
        status=Order.CREATED,
        total_price_paid=price,
        user=user,
    )
    Line.objects.create(
        order=order,
        course_key=course_key,
        description='Seat for {}'.format(course_run.title),
        price=price,
    )
    if coupon is not None:
        redeemed_coupon = RedeemedCoupon(order=order, coupon=coupon)
        redeemed_coupon.save_and_log(user)
    order.save_and_log(user)
    return order


def generate_cybersource_sa_signature(payload):
    """
    Generate an HMAC SHA256 signature for the CyberSource Secure Acceptance payload

    Args:
        payload (dict): The payload to be sent to CyberSource
    Returns:
        str: The signature
    """
    # This is documented in certain CyberSource sample applications:
    # http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_SOP/html/wwhelp/wwhimpl/js/html/wwhelp.htm#href=creating_profile.05.6.html
    keys = payload['signed_field_names'].split(',')
    message = ','.join('{}={}'.format(key, payload[key]) for key in keys)

    digest = hmac.new(
        settings.CYBERSOURCE_SECURITY_KEY.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256,
    ).digest()

    return b64encode(digest).decode('utf-8')


def make_dashboard_receipt_url(dashboard_url, course_key, status):
    """
    Generate URL that user is redirected to on successful order

    Args:
        dashboard_url (str): The absolute url for the dashboard
        course_key (str): An edX course key
        status (str): The order receipt page status, either 'cancel' or 'receipt'
    Returns:
        str:
            The URL for the order receipt page
    """
    return "{dashboard_url}?status={status}&course_key={course_key}".format(
        dashboard_url=dashboard_url,
        status=status,
        course_key=quote_plus(course_key),
    )


def generate_cybersource_sa_payload(order, dashboard_url, ip_address=None):
    """
    Generates a payload dict to send to CyberSource for Secure Acceptance

    Args:
        order (Order): An order
        dashboard_url: (str): The absolute url for the dashboard
        ip_address (str): The user's IP address
    Returns:
        dict: the payload to send to CyberSource via Secure Acceptance
    """
    # http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_WM/Secure_Acceptance_WM.pdf
    # Section: API Fields

    # Course key is used only to show the confirmation message to the user
    course_key = ""
    line = order.line_set.first()
    if line is not None:
        course_key = line.course_key
    course_run = CourseRun.objects.get(edx_course_key=course_key)

    # NOTE: be careful about max length here, many (all?) string fields have a max
    # length of 255. At the moment none of these fields should go over that, due to database
    # constraints or other reasons

    payload = {
        'access_key': settings.CYBERSOURCE_ACCESS_KEY,
        'amount': str(order.total_price_paid),
        'consumer_id': order.user.username,
        'currency': 'USD',
        'locale': 'en-us',
        'item_0_code': 'course',
        'item_0_name': '{}'.format(course_run.title),
        'item_0_quantity': 1,
        'item_0_sku': '{}'.format(course_key),
        'item_0_tax_amount': '0',
        'item_0_unit_price': str(order.total_price_paid),
        'line_item_count': 1,
        'override_custom_cancel_page': make_dashboard_receipt_url(dashboard_url, course_key, 'cancel'),
        'override_custom_receipt_page': make_dashboard_receipt_url(dashboard_url, course_key, 'receipt'),
        'reference_number': make_reference_id(order),
        'profile_id': settings.CYBERSOURCE_PROFILE_ID,
        'signed_date_time': now_in_utc().strftime(ISO_8601_FORMAT),
        'transaction_type': 'sale',
        'transaction_uuid': uuid.uuid4().hex,
        'unsigned_field_names': '',
        'merchant_defined_data1': 'course',
        'merchant_defined_data2': '{}'.format(course_run.title),
        'merchant_defined_data3': '{}'.format(course_key),
        "customer_ip_address": ip_address if ip_address else None,
    }

    field_names = sorted(list(payload.keys()) + ['signed_field_names'])
    payload['signed_field_names'] = ','.join(field_names)
    payload['signature'] = generate_cybersource_sa_signature(payload)

    return payload


def make_reference_id(order):
    """
    Make a reference id

    Args:
        order (Order):
            An order
    Returns:
        str:
            A reference number for use with CyberSource to keep track of orders
    """
    return "{}{}-{}".format(_REFERENCE_NUMBER_PREFIX, settings.CYBERSOURCE_REFERENCE_PREFIX, order.id)


def get_new_order_by_reference_number(reference_number):
    """
    Parse a reference number received from CyberSource and lookup the corresponding Order.

    Args:
        reference_number (str):
            A string which contains the order id and the instance which generated it
    Returns:
        Order:
            An order
    """
    if not reference_number.startswith(_REFERENCE_NUMBER_PREFIX):
        raise ParseException("Reference number must start with {}".format(_REFERENCE_NUMBER_PREFIX))
    reference_number = reference_number[len(_REFERENCE_NUMBER_PREFIX):]

    try:
        order_id_pos = reference_number.rindex('-')
    except ValueError:
        raise ParseException("Unable to find order number in reference number")

    try:
        order_id = int(reference_number[order_id_pos + 1:])
    except ValueError:
        raise ParseException("Unable to parse order number")

    prefix = reference_number[:order_id_pos]
    if prefix != settings.CYBERSOURCE_REFERENCE_PREFIX:
        log.error("CyberSource prefix doesn't match: %s != %s", prefix, settings.CYBERSOURCE_REFERENCE_PREFIX)
        raise ParseException("CyberSource prefix doesn't match")

    try:
        return Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        raise EcommerceException("Unable to find order {}".format(order_id))


def enroll_user_on_success(order):
    """
    Enroll user after they made a successful purchase.

    Args:
        order (Order): An order to be fulfilled

    Returns:
         None
    """
    user_social = get_edxorg_social_auth(order.user)
    enrollments_client = EdxApi(user_social.extra_data, settings.EDXORG_BASE_URL).enrollments
    existing_enrollments = enrollments_client.get_student_enrollments()

    exceptions = []
    enrollments = []
    for line in order.line_set.all():
        course_key = line.course_key
        try:
            if not existing_enrollments.is_enrolled_in(course_key):
                enrollments.append(enrollments_client.create_audit_student_enrollment(course_key))
        except Exception as ex:  # pylint: disable=broad-except
            log.exception(
                "Error creating audit enrollment for course key %s for user %s",
                course_key,
                order.user.username,
            )
            exceptions.append(ex)

    for enrollment in enrollments:
        CachedEdxDataApi.update_cached_enrollment(
            order.user,
            enrollment,
            enrollment.course_id,
            index_user=True,
        )

    if exceptions:
        raise EcommerceEdxApiException(exceptions)


def is_coupon_redeemable_for_run(coupon, user, course_key):
    """
    Returns true if the coupon is redeemable for the user for a course run.

    Args:
        coupon (Coupon): A coupon
        user (django.contrib.auth.models.User): A user
        course_key (str): An edX course key

    Returns:
        bool:
            True if a course is redeemable by a user, for the specific course run with that course key
    """
    if not is_coupon_redeemable(coupon, user):
        return False

    return course_key in coupon.course_keys


def is_coupon_redeemable(coupon, user):
    """
    Returns true if the coupon is redeemable for the user, for any relevant course run.

    Args:
        coupon (Coupon): A coupon
        user (django.contrib.auth.models.User): A user
    Returns:
        bool:
            True if the coupon is redeemable by the user for some course run
    """
    if not Program.objects.filter(
            programenrollment__user=user,
            programenrollment__program__course__courserun__edx_course_key__in=coupon.course_keys,
            live=True,
    ).exists():
        return False

    if (
            not coupon.is_valid or                      # coupon must be enabled and within valid date range
            not coupon.user_has_redemptions_left(user)  # coupon must not be used up
    ):
        return False

    if coupon.coupon_type == Coupon.DISCOUNTED_PREVIOUS_COURSE:
        # We validate in clean() that content_object is a Course if coupon_type is DISCOUNTED_PREVIOUS_RUN
        course = coupon.content_object
        program = course.program
        edx_user_data = CachedEdxUserData(user, program=program)

        mmtrack = MMTrack(
            user,
            program,
            edx_user_data,
        )

        # For this coupon type the user must have already purchased a course run on edX
        return any((mmtrack.has_verified_enrollment(run.edx_course_key) for run in course.courserun_set.all()))

    return True


def pick_coupons(user):
    """
    Choose the coupons which would be used in redemptions by the user. There should be at most one coupon
    per program in the output.

    The heuristic is currently:
     - choose attached coupons over automatic coupons
     - choose the coupon which has been most recently attached, or most recently modified

    Args:
        user (django.contrib.auth.models.User): A user

    Returns:
        list of Coupon: The coupons which will be used by the user when redeeming runs in a program
    """
    sorted_attached_coupons = Coupon.user_coupon_qset(user).order_by('-usercoupon__updated_on')
    sorted_automatic_coupons = Coupon.is_automatic_qset().order_by('-updated_on')

    # At this point there should only be coupons the user has attached (opted into by clicking a link)
    # or automatic coupons, which there should only be a few. So the next iterations should not
    # affect many rows in the DB.

    coupons = []
    # Only one coupon per program
    program_ids = set()
    for coupon in chain(sorted_attached_coupons, sorted_automatic_coupons):
        program_id = coupon.program.id
        if program_id not in program_ids and is_coupon_redeemable(coupon, user):
            coupons.append(coupon)
            program_ids.add(program_id)

    return coupons


def calculate_coupon_price(coupon, price, course_key):
    """
    Calculate the adjusted price given a coupon

    Args:
        coupon (Coupon): A coupon
        price (decimal.Decimal): A price
        course_key (str): An edX course key

    Returns:
        decimal.Decimal: An adjusted price
    """
    new_price = price
    if course_key in coupon.course_keys:
        if coupon.amount_type == Coupon.PERCENT_DISCOUNT:
            new_price = price * (1-coupon.amount)
        elif coupon.amount_type == Coupon.FIXED_DISCOUNT:
            new_price = price - coupon.amount
        elif coupon.amount_type == Coupon.FIXED_PRICE:
            new_price = coupon.amount

    if new_price < 0:
        new_price = 0
    elif new_price > price:
        new_price = price
    return new_price


def calculate_run_price(course_run, user):
    """
    Calculate the price of a course given the coupons and financial aid available to the user.

    Args:
        course_run (CourseRun): A course run
        user (django.contrib.auth.models.User): A user

    Returns:
        (decimal.Decimal, Coupon):
            The adjusted of the course, and the coupon used if any
    """
    program = course_run.course.program
    enrollment = get_object_or_404(ProgramEnrollment, program=program, user=user)
    price = get_formatted_course_price(enrollment)['price']
    coupons = [coupon for coupon in pick_coupons(user) if coupon.program == program]

    if not coupons:
        # There is no coupon for this program
        return price, None
    coupon = coupons[0]

    if course_run.edx_course_key not in coupon.course_keys:
        # coupon does not apply to this particular course run
        return price, None

    price = calculate_coupon_price(coupon, price, course_run.edx_course_key)
    return price, coupon


def validate_prices():
    """
    Validate prices and financial aid discounts
    Returns:
        list: List of validation errors
    """
    errors = []
    programs = Program.objects.filter(live=True)
    for program in programs:
        if program.financial_aid_availability:
            tier = TierProgram.objects.filter(program=program, current=True).order_by("-discount_amount").first()
            if tier:
                if tier.discount_amount > program.price:
                    errors.append('Discount is higher than course price for program {0}'.format(program.title))
                if not TierProgram.objects.filter(discount_amount=0, program=program, current=True).exists():
                    errors.append('Could not find 0 discount TierProgram for program {0}'.format(program.title))
                if not TierProgram.objects.filter(income_threshold=0, program=program, current=True).exists():
                    errors.append(
                        'Could not find 0 income_threshold TierProgram for program {0}'.format(program.title)
                    )
            else:
                errors.append('Could not find current TierProgram for program {0}'.format(program.title))

    return errors

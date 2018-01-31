"""
APIs for the grades app
"""
import logging
from collections import namedtuple

from django.contrib.auth.models import User

from django_redis import get_redis_connection

from dashboard.api_edx_cache import CachedEdxUserData, CachedEdxDataApi
from dashboard.models import CachedEnrollment, CachedCurrentGrade
from dashboard.utils import get_mmtrack
from grades.exceptions import FreezeGradeFailedException
from grades.models import (
    FinalGrade,
    FinalGradeStatus,
    MicromastersProgramCertificate,
    CombinedFinalGrade)

CACHE_KEY_FAILED_USERS_BASE_STR = "failed_users_{0}"

log = logging.getLogger(__name__)

UserFinalGrade = namedtuple('UserFinalGrade', ['grade', 'passed', 'payed_on_edx'])

COURSE_GRADE_WEIGHT = 0.4
EXAM_GRADE_WEIGHT = 0.6


def _compute_grade_for_fa(user_edx_run_data):
    """
    Gets the final grade for an user enrolled in the course run that is part of a financial aid program.

    Args:
        user_edx_run_data (dashboard.api_edx_cache.UserCachedRunData): the edx cached data for an user in a course run

    Returns:
        UserFinalGrade: a namedtuple of (float, bool,) representing the final grade
            of the user in the course run and whether she passed it
    """
    if user_edx_run_data.certificate is not None:
        run_passed = user_edx_run_data.certificate.status == 'downloadable'
        # the following line should be updated when
        # we add support for honor enrollments and certificates in the edx-api-client
        payed_on_edx = user_edx_run_data.certificate.certificate_type in ['honor', 'verified']
    else:
        run_passed = user_edx_run_data.current_grade.passed
        payed_on_edx = False
    # making sure the grade is a float
    try:
        grade = float(user_edx_run_data.current_grade.percent)
    except (ValueError, TypeError):
        grade = 0.
    return UserFinalGrade(grade=grade, passed=run_passed, payed_on_edx=payed_on_edx)


def _compute_grade_for_non_fa(user_edx_run_data):
    """
    Gets the final grade for an user enrolled in the
    course run that is part of a non financial aid program.
    If the user has a certificate, she has passed otherwise she has not.

    Args:
        user_edx_run_data (dashboard.api_edx_cache.UserCachedRunData): the edx cached data for an user in a course run

    Returns:
        UserFinalGrade: a namedtuple of (float, bool,) representing the final grade
            of the user in the course run and whether she passed it
    """
    if user_edx_run_data.certificate is not None:
        run_passed = user_edx_run_data.certificate.status == 'downloadable'
        payed_on_edx = user_edx_run_data.certificate.certificate_type in ['honor', 'verified']
    else:
        run_passed = False
        payed_on_edx = user_edx_run_data.enrollment.mode in ['honor', 'verified']
    # making sure the grade is a float
    try:
        grade = float(user_edx_run_data.current_grade.percent)
    except (ValueError, TypeError):
        grade = 0.
    return UserFinalGrade(grade=grade, passed=run_passed, payed_on_edx=payed_on_edx)


def _get_compute_func(course_run):
    """
    Gets the proper function to compute the final grade.

    Currently this implements a very simple logic, but it seems that
    in the near future we could have policies to compute the final grade
    that can be different per program (run?).

    Args:
        course_run (CourseRun): a course run model object

    Returns:
        function: a function to be called to compute the final grade
    """
    return _compute_grade_for_fa if course_run.course.program.financial_aid_availability else _compute_grade_for_non_fa


def get_final_grade(user, course_run):
    """
    Public function to compute final grades for the a user in a course run.

    Args:
        user (User): a django User
        course_run (CourseRun): a course run model object

    Returns:
        UserFinalGrade: a namedtuple of (grade, passed,) representing the final grade
            of the user in the course run and whether she passed it
    """
    # pull the cached data for the user
    user_data = CachedEdxUserData(user, course_run.course.program)
    run_data = user_data.get_run_data(course_run.edx_course_key)
    # pick the right function
    final_grade_func = _get_compute_func(course_run)
    return final_grade_func(run_data)


def get_users_without_frozen_final_grade(course_run):
    """
    Public function to extract all the users that need a final grade freeze for a course run.
    All the users that are enrolled in a course run and have a
    current grade must have frozen final grade.

    Args:
        course_run (CourseRun): a course run model object

    Returns:
        queryset: a queryset of users
    """
    # get the list of users enrolled in the course and have current grade
    users_in_cache = set(CachedEnrollment.get_cached_users(course_run)).intersection(
        set(CachedCurrentGrade.get_cached_users(course_run))
    )
    # get all the users with already frozen final grade
    users_already_processed = set(FinalGrade.get_frozen_users(course_run))
    return User.objects.filter(pk__in=users_in_cache.difference(users_already_processed))


def freeze_user_final_grade(user, course_run, raise_on_exception=False):
    """
    Public function to freeze final grades for the a user in a course run.

    Args:
        user (User): a django User
        course_run (CourseRun): a course run model object

    Returns:
        None
    """
    # no need to do anything if the course run is not ready
    if not course_run.can_freeze_grades:
        if not raise_on_exception:
            log.info(
                'The grade for user "%s" course "%s" cannot be frozen yet',
                user.username, course_run.edx_course_key
            )
            return
        else:
            raise FreezeGradeFailedException(
                'The grade for user "{0}" course "{1}" cannot be frozen yet'.format(
                    user.username,
                    course_run.edx_course_key,
                )
            )
    # update one last time the user's certificates and current grades
    try:
        CachedEdxDataApi.update_all_cached_grade_data(user)
    except Exception as ex:  # pylint: disable=broad-except
        con = get_redis_connection("redis")
        con.lpush(CACHE_KEY_FAILED_USERS_BASE_STR.format(course_run.edx_course_key), user.id)
        if not raise_on_exception:
            log.exception('Impossible to refresh the edX cache for user "%s"', user.username)
            return
        else:
            raise FreezeGradeFailedException(
                'Impossible to refresh the edX cache for user "{0}"'.format(user.username)) from ex
    # get the final grade for the user in the program
    try:
        final_grade = get_final_grade(user, course_run)
    except Exception as ex:  # pylint: disable=broad-except
        if not raise_on_exception:
            log.exception(
                'Impossible to get final grade for user "%s" in course %s', user.username, course_run.edx_course_key)
            return
        else:
            raise FreezeGradeFailedException(
                'Impossible to get final grade for user "{0}" in course {1}'.format(
                    user.username,
                    course_run.edx_course_key
                )
            ) from ex
    # the final grade at this point should not exists, but putting a `get_or_create`
    # should solve the problem when the function is called synchronously from the dashboard REST API multiple times
    final_grade_obj, _ = FinalGrade.objects.get_or_create(
        user=user,
        course_run=course_run,
        grade=final_grade.grade,
        passed=final_grade.passed,
        status=FinalGradeStatus.COMPLETE,
        course_run_paid_on_edx=final_grade.payed_on_edx
    )
    return final_grade_obj


def generate_program_certificate(user, program):
    """
    Create a program certificate if the user has a MM course certificate
    for each course in the program

    Args:
        user (User): a Django user.
        program (programs.models.Program): program where the user is enrolled.
    """
    mmtrack = get_mmtrack(user, program)

    if MicromastersProgramCertificate.objects.filter(user=user, program=program).exists():
        log.error('User [%s] already has a certificate for program [%s]', user, program)
        return

    for course in program.course_set.all():
        best_grade = mmtrack.get_best_final_grade_for_course(course)

        if best_grade is None or not best_grade.has_certificate:
            return
    MicromastersProgramCertificate.objects.create(user=user, program=program)
    log.info(
        'Created MM program certificate for [%s] in program [%s]',
        user.username,
        program.title
    )


def update_or_create_combined_final_grade(user, course):
    """
    Update or create CombinedFinalGrade

    Args:
        user (User): a django User
        course (Course): a course model object
    """
    mmtrack = get_mmtrack(user, course.program)
    final_grade = mmtrack.get_best_final_grade_for_course(course)
    if final_grade is None:
        log.error('User [%s] does not have a final for course [%s]', user, course)
        return

    best_exam = mmtrack.get_best_proctored_exam_grade(course)
    if best_exam is None:
        log.error('User [%s] does not have a passing exam grade for course [%s]', user, course)
        return

    calculated_grade = round(final_grade.grade_percent * COURSE_GRADE_WEIGHT + best_exam.score * EXAM_GRADE_WEIGHT, 1)
    combined_grade, _ = CombinedFinalGrade.objects.update_or_create(
        user=user,
        course=course,
        defaults={'grade': calculated_grade}
    )
    combined_grade.save_and_log(None)

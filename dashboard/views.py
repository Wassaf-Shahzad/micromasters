"""
Views for dashboard REST APIs
"""
import logging

from django.contrib.auth.models import User
from django.conf import settings
from django.urls import reverse
from requests.exceptions import HTTPError
from rest_framework import (
    authentication,
    permissions,
    status,
)
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from edx_api.client import EdxApi

from backends import utils
from dashboard.permissions import CanReadIfStaffOrSelf
from dashboard.serializers import UnEnrollProgramsSerializer
from dashboard.models import ProgramEnrollment
from dashboard.api import get_user_program_info
from dashboard.api_edx_cache import CachedEdxDataApi
from micromasters.exceptions import PossiblyImproperlyConfigured
from profiles.api import get_edxorg_social_auth


log = logging.getLogger(__name__)


class UserDashboard(APIView):
    """
    Class based view for user dashboard view.
    """
    authentication_classes = (
        authentication.SessionAuthentication,
        authentication.TokenAuthentication,
    )
    permission_classes = (permissions.IsAuthenticated, CanReadIfStaffOrSelf)

    def get(self, request, username, *args, **kargs):  # pylint: disable=unused-argument
        """
        Returns information needed to display the user
        dashboard for all the programs the user is enrolled in.
        """
        user = get_object_or_404(
            User,
            username=username,
        )

        # get the credentials for the current user for edX
        edx_client = None
        if user == request.user:
            user_social = get_edxorg_social_auth(request.user)
            try:
                utils.refresh_user_token(user_social)
            except utils.InvalidCredentialStored as exc:
                return Response(
                    status=exc.http_status_code,
                    data={'error': str(exc)}
                )
            except:  # pylint: disable=bare-except
                log.exception('Impossible to refresh user credentials in dashboard view')
            # create an instance of the client to query edX
            edx_client = EdxApi(user_social.extra_data, settings.EDXORG_BASE_URL)

        try:
            program_dashboard = get_user_program_info(user, edx_client)
        except utils.InvalidCredentialStored as exc:
            log.exception('Access token for user %s is fresh but invalid; forcing login.', user.username)
            return Response(
                status=exc.http_status_code,
                data={'error': str(exc)}
            )
        return Response(
            status=status.HTTP_200_OK,
            data=program_dashboard
        )


class UserCourseEnrollment(APIView):
    """
    Create an audit enrollment for the user in a given course run identified by course_id.
    """
    authentication_classes = (
        authentication.SessionAuthentication,
        authentication.TokenAuthentication,
    )
    permission_classes = (permissions.IsAuthenticated, )

    def post(self, request):
        """
        Audit enrolls the user in a course in edx
        """
        course_id = request.data.get('course_id')
        if course_id is None:
            raise ValidationError('course id missing in the request')
        # get the credentials for the current user for edX
        user_social = get_edxorg_social_auth(request.user)
        try:
            utils.refresh_user_token(user_social)
        except utils.InvalidCredentialStored as exc:
            log.error(
                "Error while refreshing credentials for user %s",
                request.user.username,
            )
            return Response(
                status=exc.http_status_code,
                data={'error': str(exc)}
            )

        # create an instance of the client to query edX
        edx_client = EdxApi(user_social.extra_data, settings.EDXORG_BASE_URL)

        try:
            enrollment = edx_client.enrollments.create_audit_student_enrollment(course_id)
        except HTTPError as exc:
            if exc.response.status_code == status.HTTP_400_BAD_REQUEST:
                raise PossiblyImproperlyConfigured(
                    'Got a 400 status code from edX server while trying to create '
                    'audit enrollment. This might happen if the course is improperly '
                    'configured on MicroMasters. Course key '
                    '{course_key}, user "{username}"'.format(
                        username=request.user.username,
                        course_key=course_id,
                    )
                )
            log.error(
                "Http error from edX while creating audit enrollment for course key %s for edX user %s",
                course_id,
                request.user,
            )
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={'error': str(exc)}
            )
        except Exception as exc:  # pylint: disable=broad-except
            log.exception(
                "Error creating audit enrollment for course key %s for user %s",
                course_id,
                request.user.username,
            )
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={'error': str(exc)}
            )
        CachedEdxDataApi.update_cached_enrollment(request.user, enrollment, enrollment.course_id, index_user=True)
        return Response(
            data=enrollment.json
        )


class UnEnrollPrograms(APIView):
    """
    api that unenroll user from one or more programs
    """
    authentication_classes = (
        authentication.SessionAuthentication,
        authentication.TokenAuthentication,
    )
    permission_classes = (permissions.IsAuthenticated, )

    def post(self, request):
        """
        unenroll from MM program(s)
        """
        response = []
        program_ids = UnEnrollProgramsSerializer(data=request.data).get_program_ids()

        program_enrollments = ProgramEnrollment.objects.filter(
            program_id__in=program_ids,
            user=request.user
        )

        for program_enrollment in program_enrollments:
            response.append({
                'program_id': program_enrollment.program_id,
                'title': program_enrollment.program.title
            })
            program_enrollment.delete()

        return Response(
            status=status.HTTP_200_OK,
            data=response
        )


class ToggelProgramEnrollmentShareHash(APIView):
    """
    API that generates or revokes share_hash for program record access
    """
    authentication_classes = (
        authentication.SessionAuthentication,
        authentication.TokenAuthentication,
    )
    permission_classes = (permissions.IsAuthenticated, )

    def post(self, request):
        """
        Generates share_hash for program record
        """
        data = request.data
        if data.get("enrollment_id"):
            program_enrollment = ProgramEnrollment.objects.filter(
                id=data.get("enrollment_id"),
                user=request.user
            ).first()
            if program_enrollment:
                share_hash = program_enrollment.get_share_hash()
                return Response(
                    status=status.HTTP_201_CREATED,
                    data={
                        "share_hash": share_hash,
                        "absolute_path": request.build_absolute_uri(
                            reverse("shared_grade_records", kwargs=dict(
                                    enrollment_id=data.get("enrollment_id"),
                                    record_share_hash=share_hash
                                )
                            )
                        )
                    }
                )
        return Response(
            status=status.HTTP_400_BAD_REQUEST,
            data={
                "error": "Provided data is not appropriate"
            }
        )

    def delete(self, request):
        """
        Revokes share_hash for program record
        """
        data = request.data
        if data.get("enrollment_id"):
            program_enrollment = ProgramEnrollment.objects.filter(
                id=data.get("enrollment_id"),
                user=request.user
            ).first()
            if program_enrollment:
                program_enrollment.revoke_share_hash()
                return Response(
                    status=status.HTTP_200_OK,
                    data={
                        "success": "share_hash has been successfully revoked"
                    }
                )
        return Response(
            status=status.HTTP_400_BAD_REQUEST,
            data={
                "error": "Provided data is not appropriate"
            }
        )

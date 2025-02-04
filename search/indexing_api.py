"""
Functions for ES indexing
"""
import logging

from django.conf import settings
from elasticsearch.helpers import bulk
from elasticsearch.exceptions import NotFoundError

from profiles.models import Profile
from profiles.serializers import ProfileSerializer
from dashboard.serializers import UserProgramSearchSerializer
from micromasters.utils import (
    chunks,
    dict_with_keys,
)
from search.connection import (
    ALL_INDEX_TYPES,
    get_aliases,
    get_default_alias,
    get_conn,
    make_alias_name,
    GLOBAL_DOC_TYPE,
    PERCOLATE_INDEX_TYPE,
    PRIVATE_ENROLLMENT_INDEX_TYPE,
    PUBLIC_ENROLLMENT_INDEX_TYPE, make_backing_index_name,
)
from search.exceptions import ReindexException
from search.util import (
    fix_nested_filter,
    open_json_stream,
)

log = logging.getLogger(__name__)

# Used for cases where we support folding of
FOLDED_SEARCHABLE_KEYWORD_TYPE = {
    'type': 'keyword',
    'fields': {
        'folded': {
            'type': 'text',
            'analyzer': 'folding',
        }
    }
}
KEYWORD_TYPE = {'type': 'keyword'}
BOOL_TYPE = {'type': 'boolean'}
DATE_TYPE = {'type': 'date', 'format': 'date'}
LONG_TYPE = {'type': 'long'}


PUBLIC_ENROLLMENT_MAPPING = {
    GLOBAL_DOC_TYPE: {
        "properties": {
            "id": LONG_TYPE,
            "user_id": LONG_TYPE,
            "profile": {
                "properties": {
                    'account_privacy': KEYWORD_TYPE,
                    'birth_country': KEYWORD_TYPE,
                    'city': KEYWORD_TYPE,
                    'country': KEYWORD_TYPE,
                    'filled_out': BOOL_TYPE,
                    'first_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'full_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'image': KEYWORD_TYPE,
                    'image_small': KEYWORD_TYPE,
                    'image_medium': KEYWORD_TYPE,
                    'last_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'romanized_first_name': KEYWORD_TYPE,
                    'romanized_last_name': KEYWORD_TYPE,
                    'preferred_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'state_or_territory': KEYWORD_TYPE,
                    'username': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'work_history': {'type': 'nested', 'properties': {
                        'city': KEYWORD_TYPE,
                        'company_name': KEYWORD_TYPE,
                        'country': KEYWORD_TYPE,
                        'id': LONG_TYPE,
                        'industry': KEYWORD_TYPE,
                        'position': KEYWORD_TYPE,
                        'start_date': DATE_TYPE,
                        'state_or_territory': KEYWORD_TYPE,
                    }},
                }
            },
            "program": {
                "properties": {
                    'id': LONG_TYPE,
                    'total_courses': LONG_TYPE,
                    'is_learner': BOOL_TYPE,
                    'enrollments': {
                        'type': 'nested',
                        'properties': {
                            'semester': KEYWORD_TYPE,
                            'course_title': KEYWORD_TYPE,
                        }
                    },
                    'course_runs': {
                        'type': 'nested',
                        'properties': {
                            'semester': KEYWORD_TYPE,
                        }
                    },
                    'courses': {
                        'type': 'nested',
                        'properties': {
                            'course_title': KEYWORD_TYPE,
                        }
                    },
                }
            }
        },
        'dynamic': 'strict',
    }
}
PRIVATE_ENROLLMENT_MAPPING = {
    GLOBAL_DOC_TYPE: {
        "properties": {
            "id": LONG_TYPE,
            "user_id": LONG_TYPE,
            "email": FOLDED_SEARCHABLE_KEYWORD_TYPE,
            "profile": {
                "properties": {
                    'account_privacy': KEYWORD_TYPE,
                    'about_me': KEYWORD_TYPE,
                    'address': KEYWORD_TYPE,
                    'agreed_to_terms_of_service': BOOL_TYPE,
                    'birth_city': KEYWORD_TYPE,
                    'birth_country': KEYWORD_TYPE,
                    'birth_state_or_territory': KEYWORD_TYPE,
                    'city': KEYWORD_TYPE,
                    'country': KEYWORD_TYPE,
                    'date_of_birth': DATE_TYPE,
                    'edx_level_of_education': KEYWORD_TYPE,
                    'education': {'type': 'nested', 'properties': {
                        'degree_name': KEYWORD_TYPE,
                        'field_of_study': KEYWORD_TYPE,
                        'graduation_date': DATE_TYPE,
                        'id': LONG_TYPE,
                        'online_degree': BOOL_TYPE,
                        'school_city': KEYWORD_TYPE,
                        'school_country': KEYWORD_TYPE,
                        'school_name': KEYWORD_TYPE,
                        'school_state_or_territory': KEYWORD_TYPE,
                    }},
                    'email': KEYWORD_TYPE,
                    'email_optin': BOOL_TYPE,
                    'filled_out': BOOL_TYPE,
                    'first_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'full_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'gender': KEYWORD_TYPE,
                    'image': KEYWORD_TYPE,
                    'image_small': KEYWORD_TYPE,
                    'image_medium': KEYWORD_TYPE,
                    'last_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'nationality': KEYWORD_TYPE,
                    'phone_number': KEYWORD_TYPE,
                    'postal_code': KEYWORD_TYPE,
                    'preferred_language': KEYWORD_TYPE,
                    'preferred_name': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'pretty_printed_student_id': KEYWORD_TYPE,
                    'romanized_first_name': KEYWORD_TYPE,
                    'romanized_last_name': KEYWORD_TYPE,
                    'state_or_territory': KEYWORD_TYPE,
                    'student_id': KEYWORD_TYPE,
                    'username': FOLDED_SEARCHABLE_KEYWORD_TYPE,
                    'work_history': {'type': 'nested', 'properties': {
                        'city': KEYWORD_TYPE,
                        'company_name': KEYWORD_TYPE,
                        'country': KEYWORD_TYPE,
                        'id': LONG_TYPE,
                        'industry': KEYWORD_TYPE,
                        'position': KEYWORD_TYPE,
                        'start_date': DATE_TYPE,
                        'state_or_territory': KEYWORD_TYPE,
                    }},
                }
            },
            "program": {
                "properties": {
                    'id': LONG_TYPE,
                    'grade_average': LONG_TYPE,
                    'num_courses_passed': LONG_TYPE,
                    'total_courses': LONG_TYPE,
                    'is_learner': BOOL_TYPE,
                    'enrollments': {
                        'type': 'nested',
                        'properties': {
                            'final_grade': LONG_TYPE,
                            'semester': KEYWORD_TYPE,
                            'course_title': KEYWORD_TYPE,
                            'status': KEYWORD_TYPE,
                            'payment_status': KEYWORD_TYPE,
                        }
                    },
                    'course_runs': {
                        'type': 'nested',
                        'properties': {
                            'semester': KEYWORD_TYPE,
                        }
                    },
                    'courses': {
                        'type': 'nested',
                        'properties': {
                            'final_grade': LONG_TYPE,
                            'course_title': KEYWORD_TYPE,
                            'status': KEYWORD_TYPE,
                            'payment_status': KEYWORD_TYPE,
                        }
                    },
                }
            }
        },
        'dynamic': 'strict'
    }
}
PERCOLATE_MAPPING = {
    GLOBAL_DOC_TYPE: {
        "properties": {
            # Other fields will be provided via dynamic mapping
            **PRIVATE_ENROLLMENT_MAPPING[GLOBAL_DOC_TYPE]["properties"],
            "query": {
                "type": "percolator"
            }
        }
    }
}

INDEX_WILDCARD = '{index_name}_*'.format(index_name=settings.ELASTICSEARCH_INDEX)


def _index_chunk(chunk, *, index):
    """
    Add/update a list of records in Elasticsearch

    Args:
        chunk (list):
            List of serialized items to index
        index (str): An Elasticsearch index

    Returns:
        int: Number of items inserted into Elasticsearch
    """

    conn = get_conn(verify_indices=[index])
    insert_count, errors = bulk(
        conn,
        chunk,
        index=index,
        doc_type=GLOBAL_DOC_TYPE,
    )
    if len(errors) > 0:
        raise ReindexException("Error during bulk insert: {errors}".format(
            errors=errors
        ))

    refresh_index(index)
    return insert_count


def _index_chunks(items, *, index, chunk_size=100):
    """
    Add/update records in Elasticsearch.

    Args:
        items (iterable):
            Iterable of serialized items to index
        index (str): An Elasticsearch index
        chunk_size (int):
            How many items to index at once.

    Returns:
        int: Number of indexed items
    """
    # Use an iterator so we can keep track of what's been indexed already
    log.info("Indexing chunk pairs, chunk_size=%d...", chunk_size)
    count = 0
    for chunk in chunks(items, chunk_size=chunk_size):
        count += _index_chunk(chunk, index=index)
        log.info("Indexed %d items...", count)
    log.info("Indexing done, refreshing index...")
    refresh_index(index)
    log.info("Finished indexing")
    return count


def _delete_item(document_id, *, index):
    """
    Helper function to delete a document

    Args:
        document_id (int): A document id
        index (str): An Elasticsearch index
    """
    conn = get_conn(verify_indices=[index])
    try:
        conn.delete(index=index, doc_type=GLOBAL_DOC_TYPE, id=document_id)
    except NotFoundError:
        # Item is already gone
        pass


def serialize_public_enrolled_user(serialized_enrolled_user):
    """
    Creates a public serialized version of an enrolled user.

    Args:
        serialized_enrolled_user(dict):
            Serialized enrolled user generated by serialize_program_enrolled_user

    Returns:
        dict:
            serialized subset of the original document sanitized for public consumption
    """
    # filter out grades, courses passed, etc
    program = dict_with_keys(
        serialized_enrolled_user['program'],
        ['id', 'enrollments', 'courses', 'is_learner', 'total_courses', 'course_runs']
    )
    program['enrollments'] = [
        dict_with_keys(enrollment, ['course_title', 'semester'])
        for enrollment in program['enrollments']
    ]
    program['courses'] = [
        dict_with_keys(enrollment, ['course_title', ])
        for enrollment in program['courses']
    ]
    program['course_runs'] = [
        dict_with_keys(enrollment, ['semester'])
        for enrollment in program['course_runs']
    ]
    # filter out private profile information
    profile = dict_with_keys(
        serialized_enrolled_user['profile'],
        [
            'first_name', 'last_name', 'preferred_name', 'full_name',
            'romanized_first_name', 'romanized_last_name',
            'image', 'image_small', 'image_medium',
            'username', 'filled_out', 'account_privacy',
            'country', 'state_or_territory', 'city',
            'birth_country', 'work_history',
        ]
    )
    return {
        'id': serialized_enrolled_user['id'],
        '_id': serialized_enrolled_user['_id'],
        'user_id': serialized_enrolled_user['user_id'],
        'profile': profile,
        'program': program,
    }


def _get_public_documents(private_documents):
    """
    Generator for private documents to be indexed given a set of program enrollments
    Args:
        private_documents (iterable of dict):
            iterable of private documents to generate public documents for
    Yields:
        for each enrollment:
            a public (learner-learner search) document
    """
    for document in private_documents:
        yield serialize_public_enrolled_user(document)


def _get_private_documents(program_enrollments):
    """
    Generator for private documents to be indexed given a set of program enrollments
    Args:
        program_enrollments(iterable of ProgramEnrollment):
            iterable of enrollments to generate documents for
    Yields:
        for each enrollment:
            a private (staff-only search) document
            a public (learner-learner search) document
    """
    for program_enrollment in program_enrollments:
        document = serialize_program_enrolled_user(program_enrollment)
        if document is None:
            continue
        yield document


def _get_percolate_documents(percolate_queries):
    """
    Generator for percolate query documents

    Args:
        percolate_queries (iterable of PercolateQuery): An iterable of PercolateQuery

    Yields:
        for each PercolateQuery:
            a document in dict form
    """
    return (_serialize_percolate_query(query) for query in percolate_queries)


def index_program_enrolled_users(
        program_enrollments, *,
        public_indices=None, private_indices=None, chunk_size=100
):
    """
    Bulk index an iterable of ProgramEnrollments

    Args:
        program_enrollments (iterable of ProgramEnrollment): An iterable of program enrollments
        public_indices (list of str): The indices to store public enrollment documents
        private_indices (list of str): The indices to store private enrollment documents
        chunk_size (int): The number of items per chunk to index
    """
    if public_indices is None:
        public_indices = get_aliases(PUBLIC_ENROLLMENT_INDEX_TYPE)

    if private_indices is None:
        private_indices = get_aliases(PRIVATE_ENROLLMENT_INDEX_TYPE)

    # Serialize to a temporary file so we don't serialize twice (serializing is expensive)
    with open_json_stream() as json_stream:
        json_stream.write_stream(
            (document for document in _get_private_documents(program_enrollments))
        )

        for index in public_indices:
            _index_chunks(
                _get_public_documents(json_stream.read_stream()),
                index=index,
                chunk_size=chunk_size,
            )

        for index in private_indices:
            _index_chunks(
                json_stream.read_stream(),
                index=index,
                chunk_size=chunk_size,
            )


def remove_program_enrolled_user(program_enrollment_id):
    """
    Remove a program-enrolled user from Elasticsearch.

    Args:
        program_enrollment_id (int): A program enrollment id which is the same as the document id to remove
    """
    public_indices = get_aliases(PUBLIC_ENROLLMENT_INDEX_TYPE)
    for index in public_indices:
        _delete_item(program_enrollment_id, index=index)

    private_indices = get_aliases(PRIVATE_ENROLLMENT_INDEX_TYPE)
    for index in private_indices:
        _delete_item(program_enrollment_id, index=index)


def serialize_program_enrolled_user(program_enrollment):
    """
    Serializes a program-enrolled user for use with Elasticsearch.

    Args:
        program_enrollment (ProgramEnrollment): A program_enrollment to serialize
    Returns:
        dict: The data to be sent to Elasticsearch or None if it shouldn't be indexed
    """
    user = program_enrollment.user
    serialized = {
        'id': program_enrollment.id,
        '_id': program_enrollment.id,
        'user_id': user.id,
        'email': user.email,
    }
    try:
        serialized['profile'] = filter_current_work(ProfileSerializer(user.profile).data)
    except Profile.DoesNotExist:
        log.exception('User %s has no profile', user.username)
        return None

    serialized['program'] = UserProgramSearchSerializer.serialize(program_enrollment)
    return serialized


def filter_current_work(profile):
    """
    Remove work_history objects that are not current
    Args:
        profile (dict): serialized user Profile
    Returns:
        dict: Profile with filtered current work_history list
    """
    return {
        **profile,
        "work_history": [work for work in profile['work_history'] if not work['end_date']]
    }


def refresh_index(index):
    """
    Refresh the Elasticsearch index
    """
    get_conn(verify_indices=[index]).indices.refresh(index=index)


def refresh_all_default_indices():
    """
    Refresh all default indexes
    """
    for index_type in ALL_INDEX_TYPES:
        alias = get_default_alias(index_type)
        refresh_index(alias)


def clear_and_create_index(index_name, *, index_type, skip_mapping=False):
    """
    Wipe and recreate index and mapping. No indexing is done.

    Args:
        index_name (str): The name of the index
        index_type (str): The index type, used to pick the mapping
        skip_mapping (bool): If true, don't set any mapping
    """
    if index_type == PERCOLATE_INDEX_TYPE:
        mapping = PERCOLATE_MAPPING
    elif index_type == PRIVATE_ENROLLMENT_INDEX_TYPE:
        mapping = PRIVATE_ENROLLMENT_MAPPING
    elif index_type == PUBLIC_ENROLLMENT_INDEX_TYPE:
        mapping = PUBLIC_ENROLLMENT_MAPPING
    else:
        raise Exception("Unknown index type")

    conn = get_conn(verify=False)
    if conn.indices.exists(index_name):
        conn.indices.delete(index_name)
    # from https://www.elastic.co/guide/en/elasticsearch/guide/current/asciifolding-token-filter.html
    conn.indices.create(index_name, body={
        'settings': {
            'index': {
                'number_of_shards': settings.ELASTICSEARCH_SHARD_COUNT,
            },
            'analysis': {
                'analyzer': {
                    'folding': {
                        'type': 'custom',
                        'tokenizer': 'standard',
                        'filter': [
                            'lowercase',
                            'asciifolding',  # remove accents if we use folding analyzer
                        ]
                    }
                }
            }
        },
        'mappings': {
            **({} if skip_mapping else mapping),
        }
    })


def delete_indices():
    """
    Drop all the indices. Used in testing.
    """
    conn = get_conn(verify=False)
    for index_type in ALL_INDEX_TYPES:
        aliases = get_aliases(index_type)
        for alias in aliases:
            if conn.indices.exists(alias):
                conn.indices.delete_alias(index=INDEX_WILDCARD, name=alias)


def _serialize_percolate_query(query):
    """
    Serialize PercolateQuery for Elasticsearch indexing

    Args:
        query (PercolateQuery): A PercolateQuery instance

    Returns:
        dict:
            This is the query dict value with `_id` set to the database id so that ES can update this in place.
    """
    return {
        **fix_nested_filter(query.query, None),
        "_id": query.id,
    }


def index_percolate_queries(percolate_queries, chunk_size=100):
    """
    Index percolate queries

    Args:
        percolate_queries (iterable of PercolateQuery):
            An iterable of PercolateQuery
        chunk_size (int): Number of queries to index per chunk

    Returns:
        int: Number of indexed items
    """
    aliases = get_aliases(PERCOLATE_INDEX_TYPE)

    count = 0
    for index in aliases:
        count = _index_chunks(
            (_serialize_percolate_query(query) for query in percolate_queries),
            index=index,
            chunk_size=chunk_size,
        )
    # All counts should be the same
    return count


def delete_percolate_query(percolate_query_id):
    """
    Remove a percolate query from Elasticsearch

    Args:
        percolate_query_id (int):
            The id of a deleted PercolateQuery
    """
    aliases = get_aliases(PERCOLATE_INDEX_TYPE)

    for index in aliases:
        _delete_item(percolate_query_id, index=index)


def delete_backing_indices(backing_indices):
    """
    Remove the temporary backing indices

    Args:
        backing_indices (list of tuples):
            A list of tuples containing the created backing indices for reindexing
    """

    conn = get_conn(verify=False)
    for new_backing_index, index_type in backing_indices:
        temp_alias = make_alias_name(index_type, is_reindexing=True)
        conn.indices.delete_alias(name=temp_alias, index=new_backing_index)


def create_backing_indices():
    """
    Creates the list of tuples that contains the backing indices names and type which is used in reindexing
    """
    conn = get_conn(verify=False)
    new_backing_public_index = make_backing_index_name()
    new_backing_private_index = make_backing_index_name()
    new_backing_percolate_index = make_backing_index_name()
    backing_index_tuples = [
        (new_backing_public_index, PUBLIC_ENROLLMENT_INDEX_TYPE),
        (new_backing_private_index, PRIVATE_ENROLLMENT_INDEX_TYPE),
        (new_backing_percolate_index, PERCOLATE_INDEX_TYPE),
    ]
    for backing_index, index_type in backing_index_tuples:
        # Clear away temp alias so we can reuse it, and create mappings
        clear_and_create_index(backing_index, index_type=index_type)
        temp_alias = make_alias_name(index_type, is_reindexing=True)
        if conn.indices.exists_alias(name=temp_alias):
            # Deletes both alias and backing indexes
            conn.indices.delete_alias(index=INDEX_WILDCARD, name=temp_alias)

        # Point temp_alias toward new backing index
        conn.indices.put_alias(index=backing_index, name=temp_alias)

    return backing_index_tuples

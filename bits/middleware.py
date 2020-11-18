from promise import is_thenable
from functools import partial
import logging
import sys
import json

log = logging.getLogger('bits.DebugGrapheneMiddleware')


class GraphqlErrorLogMiddleware(object):
    """
    Logs errors for invalid graphql queries
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if (
                response.status_code >= 400
                and response.status_code != 403
                and "graphql" in request.path.lower()
            ):

                is_logged = False
                response_json = json.loads(response.content)
                if isinstance(response_json, list):
                    for resp_item in response_json:
                        if isinstance(resp_item, dict) and "errors" in resp_item:
                            log.error(f"Graphql Error: {resp_item['errors']}")
                            is_logged = True

                elif isinstance(response_json, dict) and "errors" in response_json:
                    log.error(f"Graphql Error: {response_json['errors']}")
                    is_logged = True

                if not is_logged:
                    log.error(f"Unknown Graphql Error: {response_json}")
        except Exception as e:
            log.debug(f"Error logging Graphql Error: {e}")

        return response


from django.http import JsonResponse


class ApiAuthenticationMiddleware:
    """Answer anonymous API calls with JSON instead of an HTML login redirect.

    The browser pages keep the friendly ``/login/?next=`` flow; automation and the
    AI question endpoint get an unambiguous 401 they can act on.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/") and not request.user.is_authenticated:
            return JsonResponse({"error": "authentication_required"}, status=401)
        return self.get_response(request)

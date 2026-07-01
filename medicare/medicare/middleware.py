import traceback
import os
import tempfile

class TracebackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        tb = traceback.format_exc()
        try:
            log_path = os.path.join(tempfile.gettempdir(), 'live_traceback.txt')
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f"URL: {request.build_absolute_uri()}\n")
                f.write(f"Method: {request.method}\n")
                # Exclude password for security
                post_data = {k: v for k, v in request.POST.items() if 'password' not in k.lower()}
                f.write(f"Post Data: {post_data}\n")
                f.write(f"Exception: {str(exception)}\n\n")
                f.write(tb)
        except Exception:
            pass
        return None

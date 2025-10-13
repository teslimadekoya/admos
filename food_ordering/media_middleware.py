from django.utils.deprecation import MiddlewareMixin

class MediaCORSHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add CORS headers for media files to allow cross-origin access
    """
    
    def process_response(self, request, response):
        # Check if this is a media file request
        if request.path.startswith('/media/'):
            # Add CORS headers for media files
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
            response['Cross-Origin-Resource-Policy'] = 'cross-origin'
            response['Cross-Origin-Embedder-Policy'] = 'unsafe-none'
            response['Cross-Origin-Opener-Policy'] = 'unsafe-none'
        
        return response

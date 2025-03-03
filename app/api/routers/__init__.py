"""
API routers module for the Gmail Migrator application.
"""

def register_routers(app):
    """
    Register all API routers with the Flask application.
    
    Args:
        app (Flask): Flask application
    """
    # Import routers here to avoid circular imports
    from app.api.routers.gmail import gmail_router
    
    # Register routers
    app.register_blueprint(gmail_router, url_prefix='/api/gmail') 
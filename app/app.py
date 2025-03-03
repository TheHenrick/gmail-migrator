"""
Main Flask application factory.
"""
from flask import Flask
from flask_cors import CORS
from app.api.routers import register_routers


def create_app(testing=False):
    """
    Create and configure the Flask application.
    
    Args:
        testing (bool): Whether the app is being run in testing mode
        
    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)
    
    # Configure app
    app.config['SECRET_KEY'] = 'dev-secret-key' if testing else 'your-secret-key-here'
    app.config['TESTING'] = testing
    
    # Configure CORS
    CORS(app)
    
    # Register API routers
    register_routers(app)
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True) 
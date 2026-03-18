from flask import Flask
import config


def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    # Register blueprints
    from blueprints.admin import admin_bp
    from blueprints.user import user_bp
    from blueprints.api import api_bp
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(api_bp)

    return app


# Expose app at module level so Vercel can find it
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

from flask import Flask
from config import Config
from models import db, User
from routes.auth import auth_bp
from routes.conta import conta_bp
from routes.reservas import reservas_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(conta_bp)
    app.register_blueprint(reservas_bp)

    with app.app_context():
        db.create_all()

        if not User.query.filter_by(email="teste@universidade.pt").first():
            u = User(email="teste@universidade.pt")
            u.set_password("123456")
            db.session.add(u)
            db.session.commit()
            print("Segredo 2FA do utilizador de teste:", u.totp_secret)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

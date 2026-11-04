import os
import random
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import Blueprint, jsonify, request
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
)
from models import db, User, PasswordReset

auth_bp = Blueprint("auth", __name__)

bcrypt = Bcrypt()


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    data     = request.get_json() or {}
    email    = data.get("email", "").strip().lower()
    name     = data.get("name", "").strip()
    password = data.get("password", "")

    if not email or not name or not password:
        return jsonify({"error": "Please fill in your name, email and password."}), 400
    if len(password) < 8:
        return jsonify({"error": "Your password needs at least 8 characters."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "There is already an account with this email. Try signing in."}), 409

    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user    = User(email=email, name=name, password_hash=pw_hash)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    resp  = jsonify({
        "message": "Account created.",
        "user": {"id": user.id, "name": user.name, "email": user.email},
    })
    set_access_cookies(resp, token)
    return resp, 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json() or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "That email or password is not right. Please try again."}), 401

    token = create_access_token(identity=str(user.id))
    resp  = jsonify({
        "message": "Login successful.",
        "user": {"id": user.id, "name": user.name, "email": user.email},
    })
    set_access_cookies(resp, token)
    return resp, 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    resp = jsonify({"message": "Logged out."})
    unset_jwt_cookies(resp)
    return resp, 200


@auth_bp.route("/api/auth/change-password", methods=["POST"])
@jwt_required()
def change_password():
    data             = request.get_json() or {}
    current_password = data.get("current_password", "")
    new_password     = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "Please fill in both passwords."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Your new password needs at least 8 characters."}), 400

    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"error": "We could not find your account. Please sign in again."}), 404
    if not bcrypt.check_password_hash(user.password_hash, current_password):
        return jsonify({"error": "Your current password is not right."}), 401
    if current_password == new_password:
        return jsonify({"error": "Please choose a password that is different from your current one."}), 400

    user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    db.session.commit()
    return jsonify({"message": "Your password has been changed."}), 200


RESET_CODE_TTL_MINUTES = 15
RESET_MAX_ATTEMPTS     = 5


def _deliver_reset_code(email: str, code: str) -> str:
    host = os.getenv("SMTP_HOST")
    if host:
        try:
            msg = EmailMessage()
            msg["Subject"] = "Your PitchWeaver password code"
            msg["From"]    = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@pitchweaver.local"))
            msg["To"]      = email
            msg.set_content(
                f"Your PitchWeaver password code is {code}\n\n"
                f"It will stop working in {RESET_CODE_TTL_MINUTES} minutes. "
                "If you did not ask for this, you can ignore this email."
            )
            port = int(os.getenv("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.starttls()
                user_ = os.getenv("SMTP_USER")
                if user_:
                    smtp.login(user_, os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(msg)
            return "email"
        except Exception as exc:
            print(f"Email could not be sent ({exc}). Showing the code here instead.")

    print("\n" + "═" * 56)
    print(f"  PASSWORD RESET CODE for {email}:  {code}")
    print(f"     (valid for {RESET_CODE_TTL_MINUTES} minutes)")
    print("═" * 56 + "\n")
    return "console"


@auth_bp.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data  = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Please enter your email."}), 400

    user = User.query.filter_by(email=email).first()
    delivery = "email"
    if user:
        PasswordReset.query.filter_by(user_id=user.id, used=False).update({"used": True})
        code  = f"{random.SystemRandom().randint(0, 999999):06d}"
        reset = PasswordReset(
            user_id=user.id,
            code_hash=bcrypt.generate_password_hash(code).decode("utf-8"),
            expires_at=datetime.utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES),
        )
        db.session.add(reset)
        db.session.commit()
        delivery = _deliver_reset_code(email, code)

    return jsonify({
        "message":  "If this email has an account, we have sent you a code.",
        "delivery": delivery,
    }), 200


@auth_bp.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data         = request.get_json() or {}
    email        = data.get("email", "").strip().lower()
    code         = data.get("code", "").strip()
    new_password = data.get("new_password", "")

    if not email or not code or not new_password:
        return jsonify({"error": "Please fill in your email, code and new password."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "Your new password needs at least 8 characters."}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "That code is not right or has expired. Please ask for a new one."}), 400

    reset = (
        PasswordReset.query
        .filter_by(user_id=user.id, used=False)
        .order_by(PasswordReset.created_at.desc())
        .first()
    )
    if not reset or reset.expires_at < datetime.utcnow() or (reset.attempts or 0) >= RESET_MAX_ATTEMPTS:
        return jsonify({"error": "That code is not right or has expired. Please ask for a new one."}), 400

    if not bcrypt.check_password_hash(reset.code_hash, code):
        reset.attempts = (reset.attempts or 0) + 1
        db.session.commit()
        return jsonify({"error": "That code is not right or has expired. Please ask for a new one."}), 400

    reset.used         = True
    user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    db.session.commit()
    return jsonify({"message": "All done! You can now sign in with your new password."}), 200


@auth_bp.route("/api/auth/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user    = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "We could not find your account. Please sign in again."}), 404
    return jsonify({
        "id":                 user.id,
        "name":               user.name,
        "email":              user.email,
        "current_difficulty": user.current_difficulty,
        "created_at":         user.created_at.isoformat(),
    })

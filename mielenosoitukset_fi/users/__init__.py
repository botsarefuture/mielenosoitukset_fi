from mielenosoitukset_fi.users.BPs import user_bp, chat_ws

_BLUEPRINT_ = user_bp

_all_ = ["_BLUEPRINT_", "socketio", "chat_ws"]
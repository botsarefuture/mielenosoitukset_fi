from app import create_app

app = create_app()

if __name__ == "__main__":
    port = app.config["PORT"]
    debug = app.config["DEBUG"]

    app.run(debug=debug, port=port)
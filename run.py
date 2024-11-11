from app import create_app

app = create_app()

def main():
    # Retrieve configurations with fallback defaults
    port = app.config.get("PORT", 5000)
    debug = app.config.get("DEBUG", False)

    app.run(debug=debug, port=port)


if __name__ == "__main__":
    main()

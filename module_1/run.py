from app import create_app

if __name__ == "__main__":
    """
    Creates and runs the application at port 8080
    on the host 0.0.0.0
    """
    app = create_app()
    app.run(host="0.0.0.0", port=8080)

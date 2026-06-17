from app import create_app

# Create instance of the application
app = create_app()

if __name__ == '__main__':
    # Running in debug mode for rapid development and clear error tracing
    app.run(host='0.0.0.0', port=5000, debug=True)
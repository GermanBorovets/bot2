from app import app


if __name__ == '__main__':
	port=8080
    app.run(debug=False, host='0.0.0.0', port=port)
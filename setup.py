from cx_Freeze import setup, Executable

setup(name='bpo_socket', 
		version="1.0", 
		description="Create websocket on port 8888",
		executables = [Executable("Socket.py")]
		)

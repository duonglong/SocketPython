from cx_Freeze import setup, Executable

setup(name='bpo_socket', 
		version="0.1", 
		description="Create websocket on port 8888",
		executables = [Executable("Socket.py")]
		)
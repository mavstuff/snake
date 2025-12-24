import socket
import json
import threading
import random
import time

# Constants
CELL_NUMBER_X = 40  # 800 // 20
CELL_NUMBER_Y = 30  # 600 // 20
UPDATE_INTERVAL = 0.15  # 150ms update interval

class Snake:
    def __init__(self):
        self.body = [(5, 10), (4, 10), (3, 10)]
        self.direction = (1, 0)
        self.new_block = False

    def move_snake(self):
        if self.new_block:
            head = self.body[0]
            new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
            self.body.insert(0, new_head)
            self.new_block = False
        else:
            head = self.body[0]
            new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
            self.body.insert(0, new_head)
            self.body.pop()

    def add_block(self):
        self.new_block = True

    def check_collision(self):
        head = self.body[0]
        # Check wall collision
        if not 0 <= head[0] < CELL_NUMBER_X or not 0 <= head[1] < CELL_NUMBER_Y:
            return True
        # Check self collision
        if head in self.body[1:]:
            return True
        return False

    def get_size(self):
        return len(self.body)

    def get_position(self):
        return self.body

class Food:
    def __init__(self):
        self.position = (10, 10)

    def randomize(self, snake_body):
        while True:
            x = random.randint(0, CELL_NUMBER_X - 1)
            y = random.randint(0, CELL_NUMBER_Y - 1)
            if (x, y) not in snake_body:
                self.position = (x, y)
                break

    def get_position(self):
        return self.position

class GameState:
    def __init__(self):
        self.snake = Snake()
        self.food = Food()
        self.food.randomize(self.snake.body)
        self.score = 0
        self.game_over = False
        self.last_update_time = time.time()
        self.game_timer = 0.0
        self.food_timer = 0.0

    def update(self):
        if self.game_over:
            return

        current_time = time.time()
        elapsed = current_time - self.last_update_time

        if elapsed >= UPDATE_INTERVAL:
            self.snake.move_snake()
            self.check_food_collision()
            self.check_game_over()
            self.last_update_time = current_time
            self.game_timer += elapsed
            self.food_timer += elapsed

    def check_food_collision(self):
        if self.snake.body[0] == self.food.position:
            self.snake.add_block()
            self.score += 1
            self.food.randomize(self.snake.body)
            self.food_timer = 0.0

    def check_game_over(self):
        if self.snake.check_collision():
            self.game_over = True

    def change_direction(self, direction):
        if self.game_over:
            return

        # Prevent reverse direction
        if direction == 'UP' and self.snake.direction != (0, 1):
            self.snake.direction = (0, -1)
        elif direction == 'DOWN' and self.snake.direction != (0, -1):
            self.snake.direction = (0, 1)
        elif direction == 'LEFT' and self.snake.direction != (1, 0):
            self.snake.direction = (-1, 0)
        elif direction == 'RIGHT' and self.snake.direction != (-1, 0):
            self.snake.direction = (1, 0)

    def reset(self):
        self.snake = Snake()
        self.food = Food()
        self.food.randomize(self.snake.body)
        self.score = 0
        self.game_over = False
        self.last_update_time = time.time()
        self.game_timer = 0.0
        self.food_timer = 0.0

    def get_state(self):
        return {
            'snake_position': self.snake.get_position(),
            'snake_size': self.snake.get_size(),
            'food_position': self.food.get_position(),
            'score': self.score,
            'game_over': self.game_over,
            'game_timer': round(self.game_timer, 2),
            'food_timer': round(self.food_timer, 2)
        }

class SnakeServer:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.game_state = GameState()
        self.running = True
        self.clients = []
        self.lock = threading.Lock()

    def handle_client(self, client_socket, address):
        print(f"Client connected: {address}")
        self.clients.append(client_socket)

        try:
            while self.running:
                # Receive direction from client
                try:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break

                    message = json.loads(data)
                    direction = message.get('direction')

                    with self.lock:
                        if direction == 'RESET':
                            self.game_state.reset()
                        elif direction:
                            self.game_state.change_direction(direction)

                except json.JSONDecodeError:
                    continue
                except ConnectionResetError:
                    break

                # Send game state to client
                with self.lock:
                    state = self.game_state.get_state()
                    response = json.dumps(state)
                
                try:
                    client_socket.sendall(response.encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError):
                    break

        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            client_socket.close()
            print(f"Client disconnected: {address}")

    def game_loop(self):
        """Updates game state at regular intervals"""
        while self.running:
            with self.lock:
                self.game_state.update()
            time.sleep(UPDATE_INTERVAL / 2)  # Update more frequently than client requests

    def shutdown(self, server_socket):
        """Clean shutdown of the server"""
        print("\nShutting down server...")
        self.running = False
        
        # Close all client connections
        with self.lock:
            for client in self.clients[:]:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
        
        # Close server socket
        try:
            server_socket.close()
        except:
            pass
        
        print("Server stopped.")

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        # Set timeout so accept() doesn't block indefinitely, allowing KeyboardInterrupt
        server_socket.settimeout(1.0)

        print(f"Snake Server started on {self.host}:{self.port}")
        print("Waiting for clients... (Press Ctrl+C to stop)")

        # Start game loop thread
        game_thread = threading.Thread(target=self.game_loop, daemon=True)
        game_thread.start()

        try:
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    # Timeout is expected, continue loop to check self.running
                    continue
        except KeyboardInterrupt:
            self.shutdown(server_socket)
        except Exception as e:
            print(f"Server error: {e}")
            self.shutdown(server_socket)

if __name__ == "__main__":
    server = SnakeServer()
    server.start()


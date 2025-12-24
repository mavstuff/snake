import socket
import json
import threading
import random
import time

# Constants
CELL_NUMBER_X = 40  # 800 // 20
CELL_NUMBER_Y = 30  # 600 // 20
UPDATE_INTERVAL = 0.15  # 150ms update interval

# Available colors for snakes (RGB tuples)
SNAKE_COLORS = [
    (0, 255, 0),    # Green
    (0, 0, 255),    # Blue
    (255, 165, 0),  # Orange
    (255, 0, 255),  # Magenta
    (0, 255, 255),  # Cyan
    (255, 255, 0),  # Yellow
    (255, 192, 203), # Pink
    (128, 0, 128),  # Purple
]

class Snake:
    def __init__(self, start_pos=None):
        if start_pos is None:
            start_pos = (5, 10)
        self.body = [start_pos, (start_pos[0] - 1, start_pos[1]), (start_pos[0] - 2, start_pos[1])]
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

    def check_collision(self, all_snakes):
        head = self.body[0]
        # Check wall collision
        if not 0 <= head[0] < CELL_NUMBER_X or not 0 <= head[1] < CELL_NUMBER_Y:
            return True
        # Check self collision
        if head in self.body[1:]:
            return True
        # Check collision with other snakes
        for other_snake in all_snakes:
            if other_snake is not self:
                if head in other_snake.body:
                    return True
        return False

    def get_size(self):
        return len(self.body)

    def get_position(self):
        return self.body

class Food:
    def __init__(self):
        self.position = (10, 10)

    def randomize(self, occupied_positions):
        """Randomize food position avoiding occupied positions"""
        max_attempts = 1000
        for _ in range(max_attempts):
            x = random.randint(0, CELL_NUMBER_X - 1)
            y = random.randint(0, CELL_NUMBER_Y - 1)
            if (x, y) not in occupied_positions:
                self.position = (x, y)
                return
        # Fallback if no free position found
        self.position = (random.randint(0, CELL_NUMBER_X - 1), random.randint(0, CELL_NUMBER_Y - 1))

    def get_position(self):
        return self.position

class Player:
    def __init__(self, player_id, color, letter, start_pos=None):
        self.player_id = player_id
        self.color = color
        self.letter = letter
        self.snake = Snake(start_pos)
        self.score = 0
        self.game_over = False
        self.game_timer = 0.0
        self.food_timer = 0.0

    def reset(self, start_pos=None):
        if start_pos is None:
            start_pos = (5, 10)
        self.snake = Snake(start_pos)
        self.score = 0
        self.game_over = False
        self.game_timer = 0.0
        self.food_timer = 0.0

    def get_state(self):
        return {
            'player_id': self.player_id,
            'color': self.color,
            'letter': self.letter,
            'snake_position': self.snake.get_position(),
            'snake_size': self.snake.get_size(),
            'score': self.score,
            'game_over': self.game_over,
            'game_timer': round(self.game_timer, 2),
            'food_timer': round(self.food_timer, 2)
        }

class MultiPlayerGame:
    def __init__(self):
        self.players = {}  # player_id -> Player
        self.foods = []  # List of Food objects
        self.last_update_time = time.time()
        self.next_player_id = 0
        self.color_index = 0

    def add_player(self, letter):
        """Add a new player and return their ID and color"""
        player_id = self.next_player_id
        self.next_player_id += 1
        
        # Assign color
        color = SNAKE_COLORS[self.color_index % len(SNAKE_COLORS)]
        self.color_index += 1
        
        # Choose starting position to avoid collisions
        occupied = []
        for player in self.players.values():
            occupied.extend(player.snake.body)
        
        start_pos = (5, 5 + player_id * 5)
        while start_pos in occupied:
            start_pos = (start_pos[0] + 1, start_pos[1])
        
        player = Player(player_id, color, letter, start_pos)
        self.players[player_id] = player
        
        # Update food count to match number of players
        self.update_food_count()
        
        return player_id, color

    def remove_player(self, player_id):
        """Remove a player"""
        if player_id in self.players:
            del self.players[player_id]
            self.update_food_count()

    def update_food_count(self):
        """Ensure food count equals number of players"""
        num_players = len(self.players)
        
        # Remove excess food
        while len(self.foods) > num_players:
            self.foods.pop()
        
        # Add food if needed
        occupied = []
        for player in self.players.values():
            occupied.extend(player.snake.body)
        for food in self.foods:
            occupied.append(food.position)
        
        while len(self.foods) < num_players:
            food = Food()
            food.randomize(occupied)
            self.foods.append(food)
            occupied.append(food.position)

    def update(self):
        current_time = time.time()
        elapsed = current_time - self.last_update_time

        if elapsed >= UPDATE_INTERVAL:
            # Move all snakes
            all_snakes = [p.snake for p in self.players.values() if not p.game_over]
            for player in self.players.values():
                if not player.game_over:
                    player.snake.move_snake()
                    player.game_timer += elapsed
                    player.food_timer += elapsed

            # Check food collisions
            for player in self.players.values():
                if player.game_over:
                    continue
                player_head = player.snake.body[0]
                for food in self.foods:
                    if food.position == player_head:
                        player.snake.add_block()
                        player.score += 1
                        player.food_timer = 0.0
                        # Respawn food
                        occupied = []
                        for p in self.players.values():
                            occupied.extend(p.snake.body)
                        for f in self.foods:
                            occupied.append(f.position)
                        food.randomize(occupied)

            # Check collisions
            for player in self.players.values():
                if not player.game_over:
                    all_snakes = [p.snake for p in self.players.values()]
                    if player.snake.check_collision(all_snakes):
                        player.game_over = True

            self.last_update_time = current_time

    def change_direction(self, player_id, direction):
        if player_id not in self.players:
            return
        player = self.players[player_id]
        if player.game_over:
            return

        # Prevent reverse direction
        if direction == 'UP' and player.snake.direction != (0, 1):
            player.snake.direction = (0, -1)
        elif direction == 'DOWN' and player.snake.direction != (0, -1):
            player.snake.direction = (0, 1)
        elif direction == 'LEFT' and player.snake.direction != (1, 0):
            player.snake.direction = (-1, 0)
        elif direction == 'RIGHT' and player.snake.direction != (-1, 0):
            player.snake.direction = (1, 0)

    def reset_player(self, player_id):
        if player_id in self.players:
            occupied = []
            for p in self.players.values():
                if p.player_id != player_id:
                    occupied.extend(p.snake.body)
            start_pos = (5, 5 + player_id * 5)
            while start_pos in occupied:
                start_pos = (start_pos[0] + 1, start_pos[1])
            self.players[player_id].reset(start_pos)

    def get_state(self, player_id=None):
        """Get game state for all players"""
        players_data = [player.get_state() for player in self.players.values()]
        foods_data = [food.get_position() for food in self.foods]
        return {
            'players': players_data,
            'foods': foods_data,
            'your_player_id': player_id
        }

class SnakeServer:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.game = MultiPlayerGame()
        self.running = True
        self.clients = {}  # player_id -> (socket, address)
        self.lock = threading.Lock()

    def handle_client(self, client_socket, address):
        # Receive letter from client first
        try:
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                client_socket.close()
                return
            
            message = json.loads(data)
            letter = message.get('letter', 'A')
            
            # Validate letter (A-Z)
            if not isinstance(letter, str) or len(letter) != 1 or not letter.isalpha():
                letter = 'A'
            letter = letter.upper()
            
        except Exception as e:
            print(f"Error receiving letter from client {address}: {e}")
            client_socket.close()
            return
        
        # Add player to game
        with self.lock:
            player_id, color = self.game.add_player(letter)
            self.clients[player_id] = (client_socket, address)
        
        print(f"Client {player_id} connected: {address} (Color: {color}, Letter: {letter})")
        
        # Send initial player info
        try:
            init_message = json.dumps({
                'player_id': player_id,
                'color': color
            })
            client_socket.sendall(init_message.encode('utf-8'))
        except Exception as e:
            print(f"Error sending initial message to client {player_id}: {e}")

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
                            self.game.reset_player(player_id)
                        elif direction:
                            self.game.change_direction(player_id, direction)

                except json.JSONDecodeError:
                    continue
                except ConnectionResetError:
                    break

                # Send game state to client
                with self.lock:
                    state = self.game.get_state(player_id)
                    response = json.dumps(state)
                
                try:
                    client_socket.sendall(response.encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError):
                    break

        except Exception as e:
            print(f"Error handling client {player_id} {address}: {e}")
        finally:
            with self.lock:
                if player_id in self.clients:
                    del self.clients[player_id]
                self.game.remove_player(player_id)
            client_socket.close()
            print(f"Client {player_id} disconnected: {address}")

    def game_loop(self):
        """Updates game state at regular intervals"""
        while self.running:
            with self.lock:
                self.game.update()
            time.sleep(UPDATE_INTERVAL / 2)  # Update more frequently than client requests

    def shutdown(self, server_socket):
        """Clean shutdown of the server"""
        print("\nShutting down server...")
        self.running = False
        
        # Close all client connections
        with self.lock:
            for player_id, (client_socket, _) in list(self.clients.items()):
                try:
                    client_socket.close()
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

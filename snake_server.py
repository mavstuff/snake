import socket
import json
import threading
import random
import time
import argparse

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
            return 'wall'
        # Check self collision
        if head in self.body[1:]:
            return 'self'
        # Check collision with other snakes
        for other_snake in all_snakes:
            if other_snake is not self:
                if head in other_snake.body:
                    return 'other_player'
        return None

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
    def __init__(self, player_id, color, letter, start_pos=None, is_bot=False):
        self.player_id = player_id
        self.color = color
        self.letter = letter
        self.snake = Snake(start_pos)
        self.score = 0
        self.game_over = False
        self.game_over_reason = None
        self.game_timer = 0.0
        self.food_timer = 0.0
        self.is_bot = is_bot
        self.bot_level = None  # Set if is_bot is True

    def reset(self, start_pos=None):
        if start_pos is None:
            start_pos = (5, 10)
        self.snake = Snake(start_pos)
        self.score = 0
        self.game_over = False
        self.game_over_reason = None
        self.game_timer = 0.0
        self.food_timer = 0.0

    def get_state(self):
        return {
            'player_id': self.player_id,
            'color': self.color,
            'letter': self.letter,
            'is_bot': self.is_bot,
            'snake_position': self.snake.get_position(),
            'snake_size': self.snake.get_size(),
            'score': self.score,
            'game_over': self.game_over,
            'game_over_reason': self.game_over_reason,
            'game_timer': round(self.game_timer, 2),
            'food_timer': round(self.food_timer, 2)
        }

class BotAI:
    """AI for bot players"""
    def __init__(self, level):
        self.level = max(0, min(9, level))  # Clamp to 0-9
        # Level 0: 90% random, Level 9: 0% random
        self.random_chance = (9 - self.level) / 10.0
    
    def choose_direction(self, snake, foods, all_snakes):
        """Choose direction based on bot level"""
        # Level 9: always head to food, Level 0: mostly random
        if random.random() > self.random_chance:
            return self._move_towards_food(snake, foods, all_snakes)
        else:
            return self._random_safe_direction(snake, all_snakes)
    
    def _move_towards_food(self, snake, foods, all_snakes):
        """Move towards nearest food, preferring directions with more space to avoid self-collision"""
        if not foods:
            return self._random_safe_direction(snake, all_snakes)
        
        head = snake.body[0]
        # Find nearest food
        nearest_food = min(foods, key=lambda f: abs(f.position[0] - head[0]) + abs(f.position[1] - head[1]))
        target = nearest_food.position
        
        # Calculate desired direction
        dx = target[0] - head[0]
        dy = target[1] - head[1]
        
        # Choose direction (prefer the larger difference)
        possible_directions = []
        if dx > 0:
            possible_directions.append('RIGHT')
        elif dx < 0:
            possible_directions.append('LEFT')
        
        if dy > 0:
            possible_directions.append('DOWN')
        elif dy < 0:
            possible_directions.append('UP')
        
        # If no clear direction, use random safe direction
        if not possible_directions:
            return self._random_safe_direction(snake, all_snakes)
        
        # Evaluate each possible direction for safety and space
        dir_map = {
            'UP': (0, -1),
            'DOWN': (0, 1),
            'LEFT': (-1, 0),
            'RIGHT': (1, 0)
        }
        
        evaluated_directions = []
        for dir_name in possible_directions:
            new_dir_vec = dir_map[dir_name]
            new_head = (head[0] + new_dir_vec[0], head[1] + new_dir_vec[1])
            
            # Check bounds
            if not (0 <= new_head[0] < CELL_NUMBER_X and 0 <= new_head[1] < CELL_NUMBER_Y):
                continue
            
            # Check immediate collision
            collision = False
            for other_snake in all_snakes:
                if other_snake is snake:
                    if new_head in snake.body[1:]:
                        collision = True
                        break
                else:
                    if new_head in other_snake.body:
                        collision = True
                        break
            
            if not collision:
                # Calculate space ahead in this direction
                space_ahead = self._calculate_space_ahead(snake, dir_name, all_snakes)
                # Calculate distance to food (smaller is better)
                # Temporary head position for distance calculation
                temp_head = new_head
                distance_to_food = abs(target[0] - temp_head[0]) + abs(target[1] - temp_head[1])
                # Score: prioritize food over space (food distance is more important)
                # Only avoid if space is extremely limited (0 or 1)
                if space_ahead >= 1:
                    score = -distance_to_food * 50 + space_ahead  # Food is much more important
                else:
                    score = -distance_to_food * 10 - space_ahead * 100  # Penalize extremely limited space
                evaluated_directions.append((dir_name, score, space_ahead))
        
        if evaluated_directions:
            # Sort by score (higher is better)
            evaluated_directions.sort(key=lambda x: x[1], reverse=True)
            # Prefer direction with good space, but allow some flexibility
            best_dir = evaluated_directions[0][0]
            # If best direction has very little space, consider alternatives
            if evaluated_directions[0][2] < 2 and len(evaluated_directions) > 1:
                # Check if second best has significantly more space
                if evaluated_directions[1][2] > evaluated_directions[0][2] + 1:
                    best_dir = evaluated_directions[1][0]
            return best_dir
        
        # If no safe direction found, fall back to random safe direction
        return self._random_safe_direction(snake, all_snakes)
    
    def _calculate_space_ahead(self, snake, direction, all_snakes, look_ahead=3):
        """Calculate how much free space is available in a given direction"""
        head = snake.body[0]
        dir_map = {
            'UP': (0, -1),
            'DOWN': (0, 1),
            'LEFT': (-1, 0),
            'RIGHT': (1, 0)
        }
        direction_vec = dir_map[direction]
        
        free_space = 0
        current_pos = head
        
        for step in range(1, look_ahead + 1):
            next_pos = (current_pos[0] + direction_vec[0], current_pos[1] + direction_vec[1])
            
            # Check bounds
            if not (0 <= next_pos[0] < CELL_NUMBER_X and 0 <= next_pos[1] < CELL_NUMBER_Y):
                break
            
            # Check collisions
            collision = False
            for other_snake in all_snakes:
                if other_snake is snake:
                    # Self collision: check body (excluding tail that moves)
                    # Account for snake moving forward
                    check_body = snake.body[1:-1] if len(snake.body) > 2 else snake.body[1:]
                    if next_pos in check_body:
                        collision = True
                        break
                else:
                    # Other snake collision
                    if next_pos in other_snake.body:
                        collision = True
                        break
            
            if collision:
                break
            
            free_space += 1
            current_pos = next_pos
        
        return free_space
    
    def _random_safe_direction(self, snake, all_snakes):
        """Choose a random safe direction, preferring directions with more space"""
        current_dir = snake.direction
        directions = ['UP', 'DOWN', 'LEFT', 'RIGHT']
        dir_map = {
            'UP': (0, -1),
            'DOWN': (0, 1),
            'LEFT': (-1, 0),
            'RIGHT': (1, 0)
        }
        
        # Remove reverse direction
        reverse_map = {
            (0, -1): 'DOWN',
            (0, 1): 'UP',
            (-1, 0): 'RIGHT',
            (1, 0): 'LEFT'
        }
        reverse_dir = reverse_map.get(current_dir)
        if reverse_dir in directions:
            directions.remove(reverse_dir)
        
        # Try directions and find safe ones, scoring by available space
        safe_directions = []
        head = snake.body[0]
        
        for dir_name in directions:
            new_dir = dir_map[dir_name]
            new_head = (head[0] + new_dir[0], head[1] + new_dir[1])
            
            # Check if safe (within bounds)
            if not (0 <= new_head[0] < CELL_NUMBER_X and 0 <= new_head[1] < CELL_NUMBER_Y):
                continue
            
            # Check collision with all snakes
            collision = False
            for other_snake in all_snakes:
                # Check if new_head collides with any part of the snake body
                if other_snake is snake:
                    # Self collision: check if new_head hits body (excluding tail)
                    if new_head in snake.body[1:]:
                        collision = True
                        break
                else:
                    # Other snake collision: check entire body
                    if new_head in other_snake.body:
                        collision = True
                        break
            
            if not collision:
                # Calculate space ahead for this direction
                space_ahead = self._calculate_space_ahead(snake, dir_name, all_snakes)
                safe_directions.append((dir_name, space_ahead))
        
        if safe_directions:
            # Sort by space ahead (more space = better), but add some randomness
            safe_directions.sort(key=lambda x: x[1], reverse=True)
            # Prefer top 2 directions (if available) with weighted random
            if len(safe_directions) > 1:
                # 70% chance to pick best, 30% chance for second best
                if random.random() < 0.7:
                    return safe_directions[0][0]
                else:
                    return safe_directions[1][0]
            else:
                return safe_directions[0][0]
        
        # If no safe direction, return None (keep current - might lead to collision but better than crashing)
        return None

class MultiPlayerGame:
    def __init__(self, num_bots=0, bot_level=5):
        self.players = {}  # player_id -> Player
        self.foods = []  # List of Food objects
        self.last_update_time = time.time()
        self.next_player_id = 0
        self.color_index = 0
        self.num_bots = num_bots
        self.bot_level = bot_level
        self.bot_ais = {}  # player_id -> BotAI
        self.bot_index = 0  # Counter for assigning bot numbers 0-9
        self.bots_initialized = False  # Track if bots have been initialized
        self.last_human_alive_time = None  # Timestamp when last human player becomes alive

    def add_player(self, letter, is_bot=False):
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
        
        player = Player(player_id, color, letter, start_pos, is_bot)
        if is_bot:
            player.bot_level = self.bot_level
            self.bot_ais[player_id] = BotAI(self.bot_level)
        
        self.players[player_id] = player
        
        # Update food count to match number of players
        self.update_food_count()
        
        return player_id, color

    def remove_player(self, player_id):
        """Remove a player"""
        if player_id in self.players:
            del self.players[player_id]
            if player_id in self.bot_ais:
                del self.bot_ais[player_id]
            self.update_food_count()
    
    def initialize_bots(self):
        """Initialize bots when first human player connects"""
        if not self.bots_initialized and self.num_bots > 0:
            for i in range(self.num_bots):
                # Assign numbers 0-9 to bots (cycling if more than 10 bots)
                bot_number = str(self.bot_index % 10)
                self.bot_index += 1
                self.add_player(bot_number, is_bot=True)
            self.bots_initialized = True

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
            # Update bot directions
            all_snakes = [p.snake for p in self.players.values() if not p.game_over]
            for player_id, bot_ai in self.bot_ais.items():
                player = self.players.get(player_id)
                if player and not player.game_over:
                    direction = bot_ai.choose_direction(player.snake, self.foods, all_snakes)
                    if direction:
                        self.change_direction(player_id, direction)
            
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
                    collision_reason = player.snake.check_collision(all_snakes)
                    if collision_reason:
                        player.game_over = True
                        player.game_over_reason = collision_reason
            
            # Check if last human player is alive (for restart message)
            human_players_alive = [
                p for p in self.players.values()
                if not p.is_bot and not p.game_over
            ]
            if len(human_players_alive) == 1:
                # Last human player is alive, set timestamp if not already set
                if self.last_human_alive_time is None:
                    self.last_human_alive_time = current_time
            else:
                # Reset timestamp if there are 0 or more than 1 human players alive
                self.last_human_alive_time = None

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
    
    def reset_all_bots(self):
        """Reset all bot players"""
        for player_id, player in self.players.items():
            if player.is_bot:
                occupied = []
                for p in self.players.values():
                    if p.player_id != player_id:
                        occupied.extend(p.snake.body)
                start_pos = (5, 5 + player_id * 5)
                while start_pos in occupied:
                    start_pos = (start_pos[0] + 1, start_pos[1])
                player.reset(start_pos)
    
    def is_last_human_player(self, player_id):
        """Check if this player is the last human player alive"""
        human_players_alive = [
            p for p in self.players.values()
            if not p.is_bot and not p.game_over
        ]
        # If requesting player is alive and human, and they're the only one, return True
        if player_id in self.players:
            player = self.players[player_id]
            if not player.is_bot and not player.game_over:
                return len(human_players_alive) == 1 and human_players_alive[0].player_id == player_id
        return False
    
    def reset_all_players(self):
        """Reset all players (human and bots)"""
        for player_id, player in self.players.items():
            occupied = []
            for p in self.players.values():
                if p.player_id != player_id:
                    occupied.extend(p.snake.body)
            start_pos = (5, 5 + player_id * 5)
            while start_pos in occupied:
                start_pos = (start_pos[0] + 1, start_pos[1])
            player.reset(start_pos)

    def get_state(self, player_id=None):
        """Get game state for all players"""
        players_data = [player.get_state() for player in self.players.values()]
        foods_data = [food.get_position() for food in self.foods]
        
        # Check if last human alive message should be shown
        show_restart_message = False
        if self.last_human_alive_time is not None:
            time_since_last_human = time.time() - self.last_human_alive_time
            show_restart_message = time_since_last_human <= 5.0  # Show for 5 seconds
        
        return {
            'players': players_data,
            'foods': foods_data,
            'your_player_id': player_id,
            'show_restart_message': show_restart_message
        }

class SnakeServer:
    def __init__(self, host='localhost', port=5555, num_bots=0, bot_level=5):
        self.host = host
        self.port = port
        self.game = MultiPlayerGame(num_bots=num_bots, bot_level=bot_level)
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
            # Initialize bots when first human player connects
            if not self.game.bots_initialized:
                self.game.initialize_bots()
                if self.game.num_bots > 0:
                    print(f"Initialized {self.game.num_bots} bots at level {self.game.bot_level}")
        
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
                            # Also reset all bots when a client restarts
                            self.game.reset_all_bots()
                        elif direction == 'RESTART_ALL':
                            # Last human player can restart entire game
                            if self.game.is_last_human_player(player_id):
                                self.game.reset_all_players()
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
        if self.game.num_bots > 0:
            print(f"Bots will start when first human player connects: {self.game.num_bots} bots at level {self.game.bot_level}")
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
    parser = argparse.ArgumentParser(description='Snake Game Server')
    parser.add_argument('--bots', type=int, default=0, help='Number of bot players (default: 0)')
    parser.add_argument('--bot-level', type=int, default=5, choices=range(10), 
                        metavar='[0-9]', help='Bot difficulty level 0-9 (0=most random, 9=direct to food, default: 5)')
    parser.add_argument('--host', type=str, default='localhost', help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=5555, help='Server port (default: 5555)')
    
    args = parser.parse_args()
    
    server = SnakeServer(host=args.host, port=args.port, num_bots=args.bots, bot_level=args.bot_level)
    server.start()

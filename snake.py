import pygame
import sys
import socket
import json
import threading

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
CELL_SIZE = 20
CELL_NUMBER_X = WINDOW_WIDTH // CELL_SIZE
CELL_NUMBER_Y = WINDOW_HEIGHT // CELL_SIZE

# Network settings
SERVER_HOST = 'localhost'
SERVER_PORT = 5555

# Colors
BLACK = (0, 0, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)

# Set up the display
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption('Snake Game - Client')
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)
small_font = pygame.font.Font(None, 24)

class GameClient:
    def __init__(self):
        self.socket = None
        self.connected = False
        self.player_id = None
        self.my_color = None
        self.selected_letter = 'A'
        self.game_state = {
            'players': [],
            'foods': [],
            'your_player_id': None
        }
        self.lock = threading.Lock()
        self.init_received = False

    def connect(self, letter):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((SERVER_HOST, SERVER_PORT))
            self.connected = True
            self.selected_letter = letter
            print(f"Connected to server at {SERVER_HOST}:{SERVER_PORT}")
            
            # Send letter to server first
            try:
                letter_message = json.dumps({'letter': letter})
                self.socket.sendall(letter_message.encode('utf-8'))
            except Exception as e:
                print(f"Error sending letter: {e}")
                return False
            
            # Receive initial player info
            try:
                data = self.socket.recv(1024).decode('utf-8')
                init_data = json.loads(data)
                self.player_id = init_data.get('player_id')
                self.my_color = tuple(init_data.get('color'))
                self.init_received = True
                print(f"Assigned Player ID: {self.player_id}, Color: {self.my_color}, Letter: {letter}")
            except Exception as e:
                print(f"Error receiving initial data: {e}")
                return False
            
            # Start receiving thread
            receive_thread = threading.Thread(target=self.receive_state, daemon=True)
            receive_thread.start()
            return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False

    def send_direction(self, direction):
        if not self.connected or not self.socket:
            return
        
        try:
            message = json.dumps({'direction': direction})
            self.socket.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"Error sending direction: {e}")
            self.connected = False

    def receive_state(self):
        while self.connected:
            try:
                data = self.socket.recv(8192).decode('utf-8')
                if not data:
                    break

                state = json.loads(data)
                with self.lock:
                    self.game_state = state
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"Error receiving state: {e}")
                self.connected = False
                break

    def get_state(self):
        with self.lock:
            return self.game_state.copy()

    def disconnect(self):
        self.connected = False
        if self.socket:
            self.socket.close()

def draw_snake(snake_body, color, letter=''):
    """Draw a snake with the given color and letter at head"""
    dark_color = tuple(max(0, c - 50) for c in color)  # Darker version for border
    for i, block in enumerate(snake_body):
        x_pos = int(block[0] * CELL_SIZE)
        y_pos = int(block[1] * CELL_SIZE)
        block_rect = pygame.Rect(x_pos, y_pos, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, color, block_rect)
        pygame.draw.rect(screen, dark_color, block_rect, 2)
        
        # Draw letter on head (first block)
        if i == 0 and letter:
            # Use white text for better visibility on colored backgrounds
            letter_text = small_font.render(letter, True, WHITE)
            letter_rect = letter_text.get_rect(center=(x_pos + CELL_SIZE // 2, y_pos + CELL_SIZE // 2))
            screen.blit(letter_text, letter_rect)

def draw_game(state, my_player_id):
    screen.fill(BLACK)
    
    # Draw all foods
    foods = state.get('foods', [])
    for food_pos in foods:
        x_pos = int(food_pos[0] * CELL_SIZE)
        y_pos = int(food_pos[1] * CELL_SIZE)
        food_rect = pygame.Rect(x_pos, y_pos, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, RED, food_rect)
    
    # Draw all snakes
    players = state.get('players', [])
    for player in players:
        if player.get('game_over', False):
            continue
        snake_body = player.get('snake_position', [])
        color = tuple(player.get('color', (0, 255, 0)))
        letter = player.get('letter', '')
        draw_snake(snake_body, color, letter)
    
    # Draw scores for all players
    y_offset = 10
    for i, player in enumerate(sorted(players, key=lambda p: p.get('score', 0), reverse=True)):
        player_id = player.get('player_id', -1)
        score = player.get('score', 0)
        color = tuple(player.get('color', (255, 255, 255)))
        game_over = player.get('game_over', False)
        is_me = (player_id == my_player_id)
        letter = player.get('letter', '')
        
        # Create score text with letter indicator
        prefix = "YOU: " if is_me else f"P{player_id}: "
        status = " (DEAD)" if game_over else ""
        score_text = small_font.render(f"{prefix}[{letter}] Score: {score}{status}", True, color)
        screen.blit(score_text, (WINDOW_WIDTH - 220, y_offset))
        y_offset += 30
    
    # Draw game timer (from first player)
    if players:
        game_timer = players[0].get('game_timer', 0.0)
        timer_text = font.render(f'Time: {game_timer:.1f}s', True, WHITE)
        screen.blit(timer_text, (10, 10))

def draw_game_over(state, my_player_id):
    screen.fill(BLACK)
    
    # Find my player
    players = state.get('players', [])
    my_player = None
    for player in players:
        if player.get('player_id') == my_player_id:
            my_player = player
            break
    
    if my_player:
        score = my_player.get('score', 0)
        game_over_text = font.render(f'Game Over! Your Score: {score}', True, WHITE)
        
        # Show leaderboard
        sorted_players = sorted(players, key=lambda p: p.get('score', 0), reverse=True)
        leaderboard_text = font.render('Leaderboard:', True, WHITE)
        screen.blit(game_over_text, (WINDOW_WIDTH/2 - 150, WINDOW_HEIGHT/2 - 150))
        screen.blit(leaderboard_text, (WINDOW_WIDTH/2 - 100, WINDOW_HEIGHT/2 - 100))
        
        y_offset = WINDOW_HEIGHT/2 - 60
        for i, player in enumerate(sorted_players[:5]):  # Top 5
            player_id = player.get('player_id', -1)
            player_score = player.get('score', 0)
            color = tuple(player.get('color', (255, 255, 255)))
            letter = player.get('letter', '')
            is_me = (player_id == my_player_id)
            prefix = "YOU" if is_me else f"Player {player_id}"
            leader_text = small_font.render(f"{i+1}. {prefix} [{letter}]: {player_score}", True, color)
            screen.blit(leader_text, (WINDOW_WIDTH/2 - 100, y_offset))
            y_offset += 25
    
    restart_text = font.render('Press SPACE to restart or ESC to quit', True, WHITE)
    restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 + 150))
    screen.blit(restart_text, restart_rect)

def draw_connection_error():
    screen.fill(BLACK)
    error_text = font.render('Could not connect to server', True, RED)
    info_text = font.render('Make sure snake_server.py is running', True, WHITE)
    quit_text = font.render('Press ESC to quit', True, WHITE)
    
    error_rect = error_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 - 50))
    info_rect = info_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2))
    quit_rect = quit_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 + 50))
    
    screen.blit(error_text, error_rect)
    screen.blit(info_text, info_rect)
    screen.blit(quit_text, quit_rect)

def draw_letter_selection():
    """Display letter selection screen and return selected letter"""
    selected_letter = 'A'
    running = True
    
    while running:
        screen.fill(BLACK)
        
        # Title
        title_text = font.render('Select Your Letter (A-Z)', True, WHITE)
        title_rect = title_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 - 150))
        screen.blit(title_text, title_rect)
        
        # Current selection
        letter_text = font.render(selected_letter, True, (0, 255, 0))
        letter_rect = letter_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 - 50))
        # Draw a box around the letter
        box_rect = pygame.Rect(letter_rect.x - 20, letter_rect.y - 20, 80, 80)
        pygame.draw.rect(screen, (0, 255, 0), box_rect, 3)
        screen.blit(letter_text, letter_rect)
        
        # Instructions
        inst_text = small_font.render('Press letter key to select, ENTER to confirm', True, WHITE)
        inst_rect = inst_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 + 50))
        screen.blit(inst_text, inst_rect)
        
        pygame.display.update()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    running = False
                elif event.unicode and event.unicode.isalpha():
                    selected_letter = event.unicode.upper()
                # Arrow keys or number keys to cycle through letters
                elif event.key == pygame.K_UP or event.key == pygame.K_w:
                    # Move to previous letter
                    if selected_letter > 'A':
                        selected_letter = chr(ord(selected_letter) - 1)
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    # Move to next letter
                    if selected_letter < 'Z':
                        selected_letter = chr(ord(selected_letter) + 1)
        
        clock.tick(60)
    
    return selected_letter

def main():
    # Show letter selection screen first
    selected_letter = draw_letter_selection()
    if selected_letter is None:
        pygame.quit()
        sys.exit()
        return
    
    client = GameClient()
    
    if not client.connect(selected_letter):
        # Show connection error screen
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
            
            draw_connection_error()
            pygame.display.update()
            clock.tick(60)
        
        pygame.quit()
        sys.exit()
        return

    running = True
    pending_direction = None
    last_request_time = 0
    request_interval = 0.05  # Request state every 50ms

    while running:
        current_time = pygame.time.get_ticks() / 1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                state = client.get_state()
                players = state.get('players', [])
                
                # Check if my player is game over
                my_player = None
                for player in players:
                    if player.get('player_id') == client.player_id:
                        my_player = player
                        break
                
                if my_player and my_player.get('game_over', False):
                    if event.key == pygame.K_SPACE:
                        client.send_direction('RESET')
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                else:
                    # Arrow key controls
                    if event.key == pygame.K_UP:
                        pending_direction = 'UP'
                    elif event.key == pygame.K_DOWN:
                        pending_direction = 'DOWN'
                    elif event.key == pygame.K_LEFT:
                        pending_direction = 'LEFT'
                    elif event.key == pygame.K_RIGHT:
                        pending_direction = 'RIGHT'

        # Send pending direction or periodic update request
        if pending_direction:
            client.send_direction(pending_direction)
            pending_direction = None
        elif current_time - last_request_time >= request_interval:
            client.send_direction(None)  # Request state update
            last_request_time = current_time

        # Get current game state
        state = client.get_state()
        players = state.get('players', [])
        
        # Check if my player is game over
        my_player = None
        for player in players:
            if player.get('player_id') == client.player_id:
                my_player = player
                break
        
        # Draw game or game over screen
        if my_player and my_player.get('game_over', False):
            draw_game_over(state, client.player_id)
        else:
            draw_game(state, client.player_id)
        
        pygame.display.update()
        clock.tick(60)

    client.disconnect()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

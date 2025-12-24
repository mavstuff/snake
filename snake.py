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
GREEN = (0, 255, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)
DARK_GREEN = (0, 200, 0)

# Set up the display
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption('Snake Game - Client')
clock = pygame.time.Clock()
font = pygame.font.Font(None, 36)

class GameClient:
    def __init__(self):
        self.socket = None
        self.connected = False
        self.game_state = {
            'snake_position': [],
            'snake_size': 0,
            'food_position': (0, 0),
            'score': 0,
            'game_over': False,
            'game_timer': 0.0,
            'food_timer': 0.0
        }
        self.lock = threading.Lock()

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((SERVER_HOST, SERVER_PORT))
            self.connected = True
            print(f"Connected to server at {SERVER_HOST}:{SERVER_PORT}")
            
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
                data = self.socket.recv(4096).decode('utf-8')
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

def draw_game(state):
    screen.fill(BLACK)
    
    # Draw snake
    snake_body = state.get('snake_position', [])
    for block in snake_body:
        x_pos = int(block[0] * CELL_SIZE)
        y_pos = int(block[1] * CELL_SIZE)
        block_rect = pygame.Rect(x_pos, y_pos, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, GREEN, block_rect)
        pygame.draw.rect(screen, DARK_GREEN, block_rect, 2)
    
    # Draw food
    food_pos = state.get('food_position', (0, 0))
    x_pos = int(food_pos[0] * CELL_SIZE)
    y_pos = int(food_pos[1] * CELL_SIZE)
    food_rect = pygame.Rect(x_pos, y_pos, CELL_SIZE, CELL_SIZE)
    pygame.draw.rect(screen, RED, food_rect)
    
    # Draw score and info
    score = state.get('score', 0)
    score_text = font.render(f'Score: {score}', True, WHITE)
    screen.blit(score_text, (10, 10))
    
    game_timer = state.get('game_timer', 0.0)
    timer_text = font.render(f'Time: {game_timer:.1f}s', True, WHITE)
    screen.blit(timer_text, (10, 50))

def draw_game_over(state):
    screen.fill(BLACK)
    score = state.get('score', 0)
    game_over_text = font.render(f'Game Over! Score: {score}', True, WHITE)
    restart_text = font.render('Press SPACE to restart or ESC to quit', True, WHITE)
    game_over_rect = game_over_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 - 50))
    restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH/2, WINDOW_HEIGHT/2 + 50))
    screen.blit(game_over_text, game_over_rect)
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

def main():
    client = GameClient()
    
    if not client.connect():
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
                
                if state.get('game_over', False):
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
        
        # Draw game or game over screen
        if state.get('game_over', False):
            draw_game_over(state)
        else:
            draw_game(state)
        
        pygame.display.update()
        clock.tick(60)

    client.disconnect()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()

import random
import sys
import threading
import traceback
import pygame
import pygame.gfxdraw
from board import Game, get_all_valid_moves
from checkers import get_bot_move

HUMAN = 'r'
LEVELS = [
    ("легко", dict(depth=2, time_limit=None, noise=70)),
    ("середньо", dict(depth=5, time_limit=0.6, noise=10)),
    ("складно", dict(depth=10, time_limit=1.2, noise=3)),
]
SPEEDS = [
    ("швидко", 150, 120),
    ("нормально", 500, 260),
    ("повільно", 1000, 420),
]
REASONS = {
    'blocked': "у суперника немає ходів",
    'wiped': "у суперника немає фігур",
    'adjudicated': "перемога за перевагою",
    'idle': "40 ходів без взяття",
}
BG_COLOR = (40, 40, 40)
BOARD_LIGHT = (238, 216, 172)
BOARD_DARK = (139, 90, 43)
PIECE_RED = (200, 40, 40)
PIECE_WHITE = (240, 240, 240)
KING_MARK = (255, 215, 0)
HIGHLIGHT_SEL = (100, 200, 100)
HIGHLIGHT_MOVE = (200, 200, 100)
BTN_COLOR = (70, 70, 70)
BTN_HOVER = (100, 100, 100)
TEXT_COLOR = (255, 255, 255)
SIDEBAR_W = 300
fonts = {}

def get_font(size, bold=False):
    key = (size, bold)
    if key not in fonts:
        fonts[key] = pygame.font.SysFont("arial", size, bold=bold)
    return fonts[key]

class Layout:
    def __init__(self, width, height):
        board_area_w = width - SIDEBAR_W
        self.cell = min(board_area_w, height) // 9
        board_size = self.cell * 8
        self.offset_x = SIDEBAR_W + (board_area_w - board_size) // 2
        self.offset_y = (height - board_size) // 2

    def square(self, row, col):
        return pygame.Rect(self.offset_x + col * self.cell, self.offset_y + row * self.cell, self.cell, self.cell)

    def center(self, row, col):
        return self.square(row, col).center

    def cell_at(self, pos):
        x, y = pos
        if x < self.offset_x or x >= self.offset_x + self.cell * 8:
            return None
        if y < self.offset_y or y >= self.offset_y + self.cell * 8:
            return None
        return (y - self.offset_y) // self.cell, (x - self.offset_x) // self.cell

class AIWorker:
    def __init__(self, game, level_config):
        self.color = game.turn
        self.ply = game.ply
        self.result = None
        self.done = False
        self.stop = threading.Event()
        board = [row[:] for row in game.grid]
        history = dict(game.history_dict)
        self.thread = threading.Thread(target=self.run, args=(board, history, level_config), daemon=True)
        self.thread.start()

    def run(self, board, history, config):
        try:
            move = get_bot_move(board, self.color, history=history, stop=self.stop, **config)
        except Exception:
            traceback.print_exc()
            legal = get_all_valid_moves(board, self.color)
            move = random.choice(legal) if legal else None
        self.result = move
        self.done = True

    def cancel(self):
        self.stop.set()

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Шашки")
        self.screen = pygame.display.set_mode((900, 600))
        self.layout = Layout(*self.screen.get_size())
        self.clock = pygame.time.Clock()
        self.level_idx = 1
        self.speed_idx = 1
        self.autoplay = False
        self.hit = {}
        self.worker = None
        self.new_game()

    def new_game(self, autoplay=False):
        if self.worker:
            self.worker.cancel()
        self.game = Game(force_result=autoplay)
        self.autoplay = autoplay
        self.worker = None
        self.anim = None
        self.selected = None
        self.wait_until = pygame.time.get_ticks() + 450

    def stop_autoplay(self):
        self.autoplay = False
        self.game.force_result = False
        self.selected = None
        if self.worker and self.worker.color == HUMAN:
            self.worker.cancel()
            self.worker = None

    def play(self, move):
        now = pygame.time.get_ticks()
        _, pause, step = SPEEDS[self.speed_idx]
        before = self.game.grid
        row, col = move['from']
        piece = before[row][col]
        self.game.play(move)
        self.selected = None
        points = [move['from']] + list(move['path'])
        total = step * len(move['path'])
        self.anim = dict(board=before, piece=piece, points=points, start=now, step=step, end=now + total)
        self.wait_until = now + total + pause

    def handle(self, event):
        if event.type == pygame.QUIT:
            if self.worker:
                self.worker.cancel()
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.press('auto')
            elif event.key == pygame.K_n:
                self.press('new')
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(event.pos)

    def click(self, pos):
        for name, rect in self.hit.items():
            if rect.collidepoint(pos):
                self.press(name)
                return
        self.click_board(pos)

    def press(self, name):
        if name.startswith('level'):
            self.level_idx = int(name[5:])
        elif name == 'speed+':
            self.speed_idx = max(0, self.speed_idx - 1)
        elif name == 'speed-':
            self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)
        elif name == 'new':
            self.new_game(autoplay=False)
        elif name == 'auto':
            if self.autoplay and not self.game.over:
                self.stop_autoplay()
            else:
                self.new_game(autoplay=True)

    def click_board(self, pos):
        game = self.game
        if game.over or self.anim or self.autoplay or game.turn != HUMAN:
            return
        cell = self.layout.cell_at(pos)
        if cell is None:
            self.selected = None
            return
        if self.selected:
            for move in game.legal:
                if move['from'] == self.selected and move['to'] == cell:
                    self.play(move)
                    return
        self.selected = cell if any(move['from'] == cell for move in game.legal) else None

    def update(self):
        now = pygame.time.get_ticks()
        if self.anim:
            if now < self.anim['end']:
                return
            self.anim = None
        game = self.game
        if game.over:
            self.worker = None
            return
        ai_turn = self.autoplay or game.turn != HUMAN
        if not ai_turn:
            if self.worker:
                self.worker.cancel()
                self.worker = None
            return
        if now < self.wait_until:
            return
        if self.worker is None:
            self.worker = AIWorker(game, LEVELS[self.level_idx][1])
        elif self.worker.done:
            worker, self.worker = self.worker, None
            if worker.color == game.turn and worker.ply == game.ply and worker.result:
                self.play(worker.result)

    def draw(self):
        self.screen.fill(BG_COLOR)
        self.draw_board()
        self.draw_sidebar(self.screen.get_height())

    def draw_piece(self, cx, cy, radius, piece):
        color = PIECE_RED if piece.lower() == 'r' else PIECE_WHITE
        darker = (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40))
        pygame.gfxdraw.filled_circle(self.screen, cx, cy, radius, color)
        pygame.gfxdraw.aacircle(self.screen, cx, cy, radius, color)
        pygame.gfxdraw.aacircle(self.screen, cx, cy, radius, darker)
        pygame.gfxdraw.aacircle(self.screen, cx, cy, radius - 1, darker)
        if piece.isupper():
            king_r = radius // 2
            pygame.gfxdraw.filled_circle(self.screen, cx, cy, king_r, KING_MARK)
            pygame.gfxdraw.aacircle(self.screen, cx, cy, king_r, KING_MARK)

    def draw_board(self):
        game = self.game
        layout = self.layout
        for row in range(8):
            for col in range(8):
                color = BOARD_LIGHT if (row + col) % 2 == 0 else BOARD_DARK
                pygame.draw.rect(self.screen, color, layout.square(row, col))
        if game.last_move:
            s = pygame.Surface((layout.cell, layout.cell))
            s.set_alpha(100)
            s.fill((255, 255, 0))
            for square in [game.last_move['from']] + list(game.last_move['path']):
                self.screen.blit(s, layout.square(*square).topleft)
        human_turn = not self.autoplay and game.turn == HUMAN and not game.over and not self.anim
        if human_turn and self.selected:
            pygame.draw.rect(self.screen, HIGHLIGHT_SEL, layout.square(*self.selected), 5)
            for move in game.legal:
                if move['from'] == self.selected:
                    pygame.draw.circle(self.screen, HIGHLIGHT_MOVE, layout.center(*move['to']), layout.cell // 6)
        radius = layout.cell // 2 - int(layout.cell * 0.1)
        board = self.anim['board'] if self.anim else game.grid
        skip = self.anim['points'][0] if self.anim else None
        for row in range(8):
            for col in range(8):
                piece = board[row][col]
                if piece == '.' or (row, col) == skip:
                    continue
                cx, cy = layout.center(row, col)
                self.draw_piece(cx, cy, radius, piece)

        if self.anim:
            anim = self.anim
            elapsed = pygame.time.get_ticks() - anim['start']
            index = min(int(elapsed // anim['step']), len(anim['points']) - 2)
            t = min(1.0, (elapsed - index * anim['step']) / anim['step'])
            x0, y0 = layout.center(*anim['points'][index])
            x1, y1 = layout.center(*anim['points'][index + 1])
            cx = int(x0 + (x1 - x0) * t)
            cy = int(y0 + (y1 - y0) * t)
            self.draw_piece(cx, cy, radius, anim['piece'])

    def draw_text(self, text, size, x, y, center=False, color=TEXT_COLOR):
        font = get_font(size)
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)

    def draw_button(self, name, text, x, y, w, h):
        rect = pygame.Rect(x, y, w, h)
        self.hit[name] = rect
        color = BTN_HOVER if rect.collidepoint(pygame.mouse.get_pos()) else BTN_COLOR
        pygame.draw.rect(self.screen, color, rect)
        pygame.draw.rect(self.screen, (200, 200, 200), rect, 2)
        self.draw_text(text, 18, x + w//2, y + h//2, center=True)

    def draw_sidebar(self, height):
        self.hit = {}
        pygame.draw.rect(self.screen, (50, 50, 50), (0, 0, SIDEBAR_W, height))
        pygame.draw.line(self.screen, (200, 200, 200), (SIDEBAR_W, 0), (SIDEBAR_W, height), 2)
        y = 20
        self.draw_text("ШАШКИ", 36, SIDEBAR_W // 2, y, center=True)
        y += 50
        game = self.game
        red_count = sum(1 for row in game.grid for p in row if p.lower() == 'r')
        white_count = sum(1 for row in game.grid for p in row if p.lower() == 'w')
        self.draw_text(f"Червоні (ти): {red_count}", 20, 20, y)
        y += 30
        self.draw_text(f"Білі (бот): {white_count}", 20, 20, y)
        y += 50
        if game.over:
            if game.winner == 'draw':
                status = "Нічия"
            elif self.autoplay:
                status = "Червоні виграли" if game.winner == 'r' else "Білі виграли"
            else:
                status = "Ти виграв!" if game.winner == HUMAN else "Бот виграв!"
        elif self.autoplay:
            status = "Грають боти..."
        elif game.turn == HUMAN:
            status = "Твій хід"
        else:
            status = "Бот думає..."
        self.draw_text("Статус:", 22, 20, y)
        y += 30
        self.draw_text(status, 20, 20, y, color=(255, 200, 100))
        if game.over and game.reason in REASONS:
            self.draw_text(REASONS[game.reason], 16, 20, y + 26, color=(180, 180, 180))
        y += 60
        self.draw_text(f"Складність: {LEVELS[self.level_idx][0]}", 20, 20, y)
        y += 30
        btn_w = (SIDEBAR_W - 40) // 3
        for i in range(3):
            self.draw_button(f'level{i}', str(i+1), 20 + i*btn_w, y, btn_w - 5, 30)
        y += 50
        self.draw_text(f"Швидкість: {SPEEDS[self.speed_idx][0]}", 20, 20, y)
        y += 30
        self.draw_button('speed-', "<", 20, y, 40, 30)
        self.draw_button('speed+', ">", 80, y, 40, 30)
        y += 60
        self.draw_button('new', "Нова гра", 20, y, SIDEBAR_W - 40, 40)
        y += 50
        if self.autoplay:
            self.draw_button('auto', "Зупинити ботів", 20, y, SIDEBAR_W - 40, 40)
        else:
            self.draw_button('auto', "Бот проти бота", 20, y, SIDEBAR_W - 40, 40)
            
def main():
    app = App()
    while True:
        for event in pygame.event.get():
            app.handle(event)
        app.update()
        app.draw()
        pygame.display.flip()
        app.clock.tick(60)

if __name__ == "__main__":
    main()
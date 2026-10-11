import random

DIRS = {'r': [(-1, -1), (-1, 1)], 'w': [(1, -1), (1, 1)]}
ALL_DIRS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
KINGS_ROW = {'r': 0, 'w': 7}
PAWN_W = 100
KING_W = 300
MAX_IDLE_MOVES = 40

def get_enemy(color):
    return 'w' if color == 'r' else 'r'

def init_grid():
    grid = [['.'] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 1:
                if r < 3: grid[r][c] = 'w'
                elif r > 4: grid[r][c] = 'r'
    return grid

def is_valid_pos(r, c):
    return 0 <= r < 8 and 0 <= c < 8

def search_jumps(grid, r, c, color, is_king, captured_list, curr_path):
    chains = []
    for dr, dc in ALL_DIRS:
        nr, nc = r + dr, c + dc
        while is_king and is_valid_pos(nr, nc) and grid[nr][nc] == '.':
            nr += dr
            nc += dc
        if not is_valid_pos(nr, nc): continue
        victim = grid[nr][nc]
        if victim == '.' or victim.lower() == color or (nr, nc) in captured_list:
            continue
        landings = []
        lr, lc = nr + dr, nc + dc
        while is_valid_pos(lr, lc) and grid[lr][lc] == '.':
            landings.append((lr, lc))
            if not is_king: break
            lr += dr
            lc += dc
        continued = []
        finished = []
        for lr, lc in landings:
            new_path = curr_path + [(lr, lc)]
            new_captured = captured_list + [(nr, nc)]
            now_king = is_king or lr == KINGS_ROW[color]
            more = search_jumps(grid, lr, lc, color, now_king, new_captured, new_path)
            if more: continued.extend(more)
            else: finished.append((new_path, new_captured))
        chains.extend(continued or finished)
    return chains

def get_simple_moves(grid, r, c, color, is_king):
    moves = []
    for dr, dc in (ALL_DIRS if is_king else DIRS[color]):
        nr, nc = r + dr, c + dc
        while is_valid_pos(nr, nc) and grid[nr][nc] == '.':
            moves.append({'from': (r, c), 'to': (nr, nc), 'captured': [], 'path': [(nr, nc)]})
            if not is_king: break
            nr += dr
            nc += dc
    return moves

def get_all_valid_moves(grid, color):
    captures = []
    quiets = []
    for r in range(8):
        for c in range(8):
            p = grid[r][c]
            if p == '.' or p.lower() != color: continue
            is_king = p.isupper()
            grid[r][c] = '.'
            chains = search_jumps(grid, r, c, color, is_king, [], [])
            grid[r][c] = p
            seen_moves = set()
            for path, cap_list in chains:
                key = (path[-1], frozenset(cap_list))
                if key not in seen_moves:
                    seen_moves.add(key)
                    captures.append({'from': (r, c), 'to': path[-1], 'captured': cap_list, 'path': path})
            if not captures:
                quiets.extend(get_simple_moves(grid, r, c, color, is_king))
    return captures if len(captures) > 0 else quiets

def do_move(grid, move):
    new_grid = [line[:] for line in grid]
    r, c = move['from']
    p = new_grid[r][c]
    new_grid[r][c] = '.'
    for cr, cc in move['captured']:
        new_grid[cr][cc] = '.'
    if p.islower() and any(pr == KINGS_ROW[p] for pr, pc in move['path']):
        p = p.upper()
    tr, tc = move['to']
    new_grid[tr][tc] = p
    return new_grid

def get_board_hash(grid, turn):
    return ''.join(''.join(row) for row in grid) + turn

def calc_stats(grid, color):
    men = 0
    kings = 0
    adv = 0
    for r in range(8):
        for c in range(8):
            p = grid[r][c]
            if p == '.' or p.lower() != color: continue
            if p.isupper():
                kings += 1
            else:
                men += 1
                adv += (7 - r) if color == 'r' else r
    mat = men * PAWN_W + kings * KING_W
    return mat, kings, adv, len(get_all_valid_moves(grid, color))

def force_winner(grid):
    red = calc_stats(grid, 'r')
    white = calc_stats(grid, 'w')
    if red > white: return 'r'
    if white > red: return 'w'
    return random.choice(['r', 'w'])

class Game:
    def __init__(self, force_result=False):
        self.grid = init_grid()
        self.turn = 'r'
        self.idle_moves = 0
        self.ply = 0
        self.winner = None
        self.reason = None
        self.force_result = force_result
        self.last_move = None
        self.history_dict = {}
        self.save_state()
        self.legal = get_all_valid_moves(self.grid, self.turn)

    @property
    def over(self):
        return self.winner is not None

    def save_state(self):
        k = get_board_hash(self.grid, self.turn)
        self.history_dict[k] = self.history_dict.get(k, 0) + 1

    def play(self, move):
        if self.over: return
        r, c = move['from']
        p = self.grid[r][c]
        made_progress = bool(move['captured']) or p.islower()
        self.grid = do_move(self.grid, move)
        self.last_move = move
        self.ply += 1
        self.idle_moves = 0 if made_progress else self.idle_moves + 1
        self.turn = get_enemy(self.turn)
        self.save_state()
        self.legal = get_all_valid_moves(self.grid, self.turn)
        self.check_if_end()

    def check_if_end(self):
        if not self.legal:
            self.winner = get_enemy(self.turn)
            has_p = any(p != '.' and p.lower() == self.turn for line in self.grid for p in line)
            self.reason = 'blocked' if has_p else 'wiped'
        elif self.idle_moves >= MAX_IDLE_MOVES:
            if self.force_result:
                self.winner = force_winner(self.grid)
                self.reason = 'adjudicated'
            else:
                self.winner = 'draw'
                self.reason = 'idle'
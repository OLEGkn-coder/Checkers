import random
import time
from board import get_all_valid_moves, do_move, get_board_hash, get_enemy, PAWN_W, KING_W

WIN_SCORE = 100000
MAX_EXT = 6
EXCHANGE_BONUS = 900
REP_PENALTY = 30
ADV_BONUS = [0, 2, 5, 9, 14, 20, 30]

def get_mid_bonus(r, c):
    ring = int(max(abs(r - 3.5), abs(c - 3.5)) - 0.5)
    return (3 - ring) * 2
MID_MATRIX = [[get_mid_bonus(r, c) for c in range(8)] for r in range(8)]

def calc_score(grid, color):
    
    opp = get_enemy(color)
    mat_score = {'r': 0, 'w': 0}
    pos_score = {'r': 0, 'w': 0}
    home_row = {'r': 0, 'w': 0}
    p_pos = {'r': [], 'w': []}
    k_pos = {'r': [], 'w': []}
    for r in range(8):
        for c in range(8):
            p = grid[r][c]
            if p == '.': continue
            s = p.lower()
            p_pos[s].append((r, c))
            pos_score[s] += MID_MATRIX[r][c]
            if p.isupper():
                mat_score[s] += KING_W
                k_pos[s].append((r, c))
            else:
                mat_score[s] += PAWN_W
                steps = (7 - r) if s == 'r' else r
                pos_score[s] += ADV_BONUS[steps]
                if steps == 0: home_row[s] += 1
    piece_count = len(p_pos['r']) + len(p_pos['w'])
    if piece_count > 10:
        for s in ['r', 'w']:
            pos_score[s] += 7 * home_row[s]
    diff = mat_score[color] - mat_score[opp]
    total = diff + pos_score[color] - pos_score[opp]
    sum_mat = mat_score['r'] + mat_score['w']
    if sum_mat:
        total += diff * EXCHANGE_BONUS // sum_mat
    if diff != 0 and piece_count <= 8:
        leader = color if diff > 0 else opp
        targets = p_pos[get_enemy(leader)]
        hunt_bonus = 0
        if targets:
            for r1, c1 in k_pos[leader]:
                nearest = min(max(abs(r1 - r2), abs(c1 - c2)) for r2, c2 in targets)
                hunt_bonus += (8 - nearest) * 10
        total += hunt_bonus if leader == color else -hunt_bonus
    return total

class BotTimeout(Exception):
    pass

class BotContext:
    def __init__(self, deadline, stop):
        self.deadline = deadline
        self.stop = stop
        self.nodes = 0

def capture_count(move):
    return len(move['captured'])

def negamax(grid, depth, alpha, beta, color, opp, ply, extensions, ctx):
    ctx.nodes += 1
    if ctx.nodes % 256 == 0:
        if ctx.stop is not None and ctx.stop.is_set():
            raise BotTimeout
        if ctx.deadline is not None and time.perf_counter() > ctx.deadline:
            raise BotTimeout
    moves = get_all_valid_moves(grid, color)
    if not moves: return -WIN_SCORE + ply
    if depth <= 0:
        if moves[0]['captured'] and extensions < MAX_EXT:
            depth = 1
            extensions += 1
        else:
            return calc_score(grid, color)
    if len(moves) > 1:
        moves.sort(key=capture_count, reverse=True)
    best = -float('inf')
    for m in moves:
        next_grid = do_move(grid, m)
        val = -negamax(next_grid, depth - 1, -beta, -alpha, opp, color, ply + 1, extensions, ctx)
        if val > best: best = val
        if best > alpha: alpha = best
        if alpha >= beta: break
    return best

def root_search(grid, moves, depth, ai, human, ctx, margin, history):
    best = -float('inf')
    results = []
    for m in moves:
        next_grid = do_move(grid, m)
        alpha = best - margin
        val = -negamax(next_grid, depth - 1, -float('inf'), -alpha, human, ai, 1, 0, ctx)
        is_exact = val > alpha
        if history and is_exact:
            val -= REP_PENALTY * history.get(get_board_hash(next_grid, human), 0)
        results.append((val, m, is_exact))
        if val > best: best = val
    return results

def get_bot_move(grid, ai, human=None, depth=4, time_limit=None, noise=0, history=None, stop=None):
    human = human or get_enemy(ai)
    moves = get_all_valid_moves(grid, ai)
    if not moves: return None
    if len(moves) == 1: return moves[0]
    deadline = time.perf_counter() + time_limit if time_limit else None
    ctx = BotContext(deadline, stop)
    scored = [(0, m, True) for m in moves]
    ordered = moves
    for cur_depth in range(1, max(1, depth) + 1):
        try:
            scored = root_search(grid, ordered, cur_depth, ai, human, ctx, noise, history)
        except BotTimeout:
            break
        ordered = [m for _, m, _ in sorted(scored, key=lambda i: -i[0])]
        if max(s for s, _, _ in scored) > WIN_SCORE // 2:
            break
    top_score = max(s for s, _, _ in scored)
    margin = 0 if abs(top_score) > WIN_SCORE // 2 else noise
    best_moves = [m for s, m, exact in scored if exact and s >= top_score - margin]
    return random.choice(best_moves) if best_moves else ordered[0]
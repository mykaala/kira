import pytest

from bots import play_random


@pytest.mark.parametrize("n", [5, 6, 7, 8, 9])
def test_thousand_random_games_finish(n):
    for seed in range(200):
        state = play_random(seed, n=n)
        assert state.winner in {"village", "mafia"}, f"seed {seed} n {n} did not finish"
        assert state.day <= 4 * n, "game ran too many days"  # saves and tied votes can stall a day
        alive = state.alive()
        mafia = sum(p.role == "mafia" for p in alive)
        assert mafia == 0 or mafia >= len(alive) - mafia


def test_same_seed_same_game():
    a, b = play_random(42), play_random(42)
    assert a.model_dump() == b.model_dump()

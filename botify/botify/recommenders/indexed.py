import random

from .random import Random
from .recommender import Recommender


class Indexed(Recommender):
    """
    Seminar 4
    """
    def __init__(self, tracks_redis, recommendations_redis, catalog):
        self.recommendations_redis = recommendations_redis
        self.fallback = Random(tracks_redis)
        self.catalog = catalog

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        recommendations = self.recommendations_redis.get(user)  # достаем из radis'а рекомендации user'а
        if recommendations is not None:
            shuffled = list(self.catalog.from_bytes(recommendations))
            random.shuffle(shuffled)
            return shuffled[0]  # выбираем случайную
        else:  # нет рекомендаций для пользователя
            return self.fallback.recommend_next(user, prev_track, prev_track_time)  # даем рандомную

from .random import Random
from .recommender import Recommender
import random


class Contextual(Recommender):
    """
    Seminar 5
    Recommend tracks closest to the previous one.
    Fall back to the random recommender if no
    recommendations found for the track.
    """

    def __init__(self, tracks_redis, catalog):
        self.tracks_redis = tracks_redis
        self.fallback = Random(tracks_redis)
        self.catalog = catalog

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        # забираем предыдущий трек
        previous_track = self.tracks_redis.get(prev_track)
        if previous_track is None:  # не нашли - рандом
            return self.fallback.recommend_next(user, prev_track, prev_track_time)

        previous_track = self.catalog.from_bytes(previous_track)
        recommendations = previous_track.recommendations  # подтягиваем рекомендации
        if not recommendations:  # если их нет - даем рандом
            return self.fallback.recommend_next(user, prev_track, prev_track_time)

        shuffled = list(recommendations)
        random.shuffle(shuffled)
        return shuffled[0]  # берем случайный трек из рекомендаций


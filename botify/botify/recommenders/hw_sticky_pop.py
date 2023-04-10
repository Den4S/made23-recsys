import random
from typing import List, Dict

from .random import Random
from .sticky_artist import StickyArtist
from .toppop import TopPop
from .recommender import Recommender


class StickyPop(Recommender):
    """
    Homework
    Try to combine two simple reccommenders:
        - sticky_artist (recommend one artist for the user)
        - top pop (randomly giving tracks from the top)
    P.S. Keep in mind that we can always use the Random recommender if we have no options.)
    """
    def __init__(self,
                 tracks_redis,
                 artists_redis,  # artists and their tracks
                 catalog,
                 users_likes: Dict[int, List[int]],
                 users_dislikes: Dict[int, List[int]]):
        # recommenders
        self.random = Random(tracks_redis)
        self.toppop = TopPop(tracks_redis, catalog.top_tracks[:100])  # top 100
        self.sticky_artist = StickyArtist(tracks_redis, artists_redis, catalog)
        # the time threshold to understand if the user liked (res>=TH) the track or not (res<TH)
        self.good_threshold = 0.5
        self.repeat_liked_threshold = 0.2
        self.toppop_threshold = 0.9
        # user history instances (everywhere key is a user ID)
        self.users_likes = users_likes  # value: list of all liked tracks id
        self.users_dislikes = users_dislikes  # value: list of all disliked tracks id

    def liked_prev_track(self, user: int, prev_track: int):
        """
        To do if the last track was good
        """
        if user in self.users_likes.keys():  # if the key exists
            if prev_track in self.users_likes[user]:
                self.users_likes[user].remove(prev_track)  # if track was already liked
            self.users_likes[user].append(prev_track)  # move it to the end of the likes
        else:
            self.users_likes[user] = [prev_track]  # create first elem in likes
        if user in self.users_dislikes.keys():  # if dislikes exists for the user
            if prev_track in self.users_dislikes[user]:
                self.users_dislikes[user].remove(prev_track)  # if track was previously disliked -- remove from dislikes

    def disliked_prev_track(self, user: int, prev_track: int):
        """
        To do if the last track was bad
        """
        if user in self.users_dislikes.keys():
            if prev_track not in self.users_dislikes[user]:  # if track was already disliked
                self.users_dislikes[user].append(prev_track)  # add it to dislikes (order doesn't matter)
        else:
            self.users_dislikes[user] = [prev_track]  # create first elem in dislikes
        if user in self.users_likes.keys():  # if likes exists
            if prev_track in self.users_likes[user]:
                self.users_likes[user].remove(prev_track)  # if track was previously disliked -- remove from dislikes

    def recommend_next(self, user: int, prev_track: int, prev_track_time: float) -> int:
        # generate random track from pop
        track_from_pop = self.toppop.recommend_next(user, prev_track, prev_track_time)

        if prev_track_time >= self.good_threshold:
            # TRACK WAS GOOD
            self.liked_prev_track(user, prev_track)
            # in the case when the previous track was liked by user recommend the
            track_of_last_liked_artist = self.sticky_artist.recommend_next(user, prev_track, prev_track_time)

            # check if track is not from alredy disliked tracks
            if user not in self.users_dislikes.keys():  # no dislikes
                return track_of_last_liked_artist  # recommend
            elif track_of_last_liked_artist in self.users_dislikes[user]:  # track from the artist is disliked
                return track_from_pop  # return the track from top
            else:  # there are dislikes, but track_of_last_liked_artist is not disliked
                # self.users_likes[user] is not empty here!
                if track_of_last_liked_artist in self.users_likes[user]:  # if proposed track is already liked
                    if random.random() < self.repeat_liked_threshold:  # return it with a probability
                        return track_of_last_liked_artist
                    # else -> return rundom in the end
                else:  # not in likes, not in dislikes
                    return track_of_last_liked_artist
        else:
            # TRACK WAS BAD
            self.disliked_prev_track(user, prev_track)
            if random.random() <= self.toppop_threshold:
                # recommend something from top with the probability self.toppop_threshold
                return track_from_pop
        # else -- random from liked:)
        # if user in self.users_likes.keys():
        #     shuffled = self.users_likes[user]
        #     random.shuffle(shuffled)
        #     return shuffled[0]
        # final random:)
        return self.random.recommend_next(user, prev_track, prev_track_time)
import math

class Attacker:
    def __init__(self):
        # A dictionary to store active tracks (the most recent BSM for a given pseudonym)
        # pseudonym -> {x, y, speed, angle, timestamp}
        self.active_tracks = {}

        # A dictionary mapping each tracked path ID to a list of its BSMs
        # This represents the reconstructed routes by the attacker
        # track_id -> [bsm1, bsm2, ...]
        self.reconstructed_routes = {}

        # A mapping of pseudonym to the current assigned track_id by the attacker
        self.pseudonym_to_track_id = {}

        # A running counter to generate new track IDs
        self.next_track_id = 1

        # Keep track of when pseudonyms are last seen to identify "disappearances"
        self.last_seen = {}

    def distance(self, x1, y1, x2, y2):
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def process_bsm(self, pseudonym, x, y, speed, angle, timestamp):
        bsm = {
            "pseudonym": pseudonym,
            "x": x,
            "y": y,
            "speed": speed,
            "angle": angle,
            "timestamp": timestamp
        }

        # If we have seen this pseudonym before and recently
        if pseudonym in self.active_tracks and self.last_seen.get(pseudonym, -1) == timestamp - 1:
            # Continue the existing track
            track_id = self.pseudonym_to_track_id[pseudonym]
            self.reconstructed_routes[track_id].append(bsm)
            self.active_tracks[pseudonym] = bsm
            self.last_seen[pseudonym] = timestamp
            return

        # If it's a new pseudonym (or reappeared after a long time), try to link it
        # to a recently disappeared pseudonym
        best_match_pseudonym = None
        min_distance = float('inf')

        # Look for pseudonyms that disappeared in the previous step
        for old_pseudo, last_bsm in self.active_tracks.items():
            if self.last_seen[old_pseudo] == timestamp - 1:
                # Plausible distance check based on speed
                # D = V * t (where t=1s since we check last step)
                max_plausible_distance = last_bsm["speed"] * 1.5 + 10.0 # Add some buffer for acceleration/error

                dist = self.distance(last_bsm["x"], last_bsm["y"], x, y)
                if dist <= max_plausible_distance and dist < min_distance:
                    min_distance = dist
                    best_match_pseudonym = old_pseudo

        if best_match_pseudonym is not None:
            # We found a match! Link the new pseudonym to the old track
            track_id = self.pseudonym_to_track_id[best_match_pseudonym]

            # Map new pseudonym to this track ID
            self.pseudonym_to_track_id[pseudonym] = track_id
            self.reconstructed_routes[track_id].append(bsm)

            # Remove old pseudonym from active tracks since we linked it
            del self.active_tracks[best_match_pseudonym]
            del self.pseudonym_to_track_id[best_match_pseudonym]

            # Update active tracks with new pseudonym
            self.active_tracks[pseudonym] = bsm
            self.last_seen[pseudonym] = timestamp
            self.pseudonym_to_track_id[pseudonym] = track_id
        else:
            # No plausible match found, start a new track
            track_id = self.next_track_id
            self.next_track_id += 1

            self.pseudonym_to_track_id[pseudonym] = track_id
            self.reconstructed_routes[track_id] = [bsm]

            self.active_tracks[pseudonym] = bsm
            self.last_seen[pseudonym] = timestamp

    def cleanup_old_tracks(self, current_timestamp, timeout=5):
        # Optional: remove tracks that haven't been seen for a while from active_tracks
        to_delete = []
        for pseudo, last_time in self.last_seen.items():
            if current_timestamp - last_time > timeout:
                to_delete.append(pseudo)

        for pseudo in to_delete:
            if pseudo in self.active_tracks:
                del self.active_tracks[pseudo]
            if pseudo in self.pseudonym_to_track_id:
                del self.pseudonym_to_track_id[pseudo]
            # keep self.last_seen for reference, or delete it too
            del self.last_seen[pseudo]

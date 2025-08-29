# Implemented by /u/Crazymajor

import re
from collections import deque


# ============================ Load Locations by Region ============================

# Builds location_to_region by reading Locations.txt
# Assumes file lists region names followed by their locations
location_to_region = {}

with open("Locations.txt", "r") as file:
    current_region = None
    for line in file:
        stripped = line.strip()
        if not stripped:
            continue
        # Detect region headers by known region names
        if stripped in {
            "North", "Riverlands", "Vale", "Iron Islands",
            "Crownlands", "Westerlands", "Reach",
            "Stormlands", "Dorne"
        }:
            current_region = stripped
        else:
            # Map location to its region
            location_to_region[stripped] = current_region

# ============================ Region Travel Connections ============================

# Defines which regions are considered neighbors (direct travel) vs. distant (requires intermediate regions)
region_travel_map = {
    "North": {"neighbours": ["Riverlands", "Vale", "Iron Islands"], "distant": ["Crownlands", "Westerlands", "Reach", "Stormlands", "Dorne"]},
    "Riverlands": {"neighbours": ["North", "Vale", "Iron Islands", "Crownlands", "Westerlands", "Reach"], "distant": ["Stormlands", "Dorne"]},
    "Vale": {"neighbours": ["North", "Riverlands", "Crownlands"], "distant": ["Iron Islands", "Westerlands", "Reach", "Stormlands", "Dorne"]},
    "Iron Islands": {"neighbours": ["North", "Riverlands", "Westerlands", "Reach"], "distant": ["Vale", "Crownlands", "Stormlands", "Dorne"]},
    "Crownlands": {"neighbours": ["Riverlands", "Vale", "Reach", "Stormlands"], "distant": ["North", "Iron Islands", "Westerlands", "Dorne"]},
    "Westerlands": {"neighbours": ["Riverlands", "Iron Islands", "Reach"], "distant": ["North", "Vale", "Crownlands", "Stormlands", "Dorne"]},
    "Reach": {"neighbours": ["Riverlands", "Iron Islands", "Crownlands", "Westerlands", "Stormlands", "Dorne"], "distant": ["North", "Vale"]},
    "Stormlands": {"neighbours": ["Crownlands", "Reach", "Dorne"], "distant": ["North", "Riverlands", "Vale", "Iron Islands", "Westerlands"]},
    "Dorne": {"neighbours": ["Reach", "Stormlands"], "distant": ["North", "Riverlands", "Vale", "Iron Islands", "Crownlands", "Westerlands"]}
}

# ============================ TPHandler Class ============================

class TPHandler:
    def __init__(self, comment):
        self.comment = comment
        self.lines = [line.strip() for line in comment.body.strip().splitlines() if line.strip()]

    # Parse month/half (e.g., "4A") from provided line
    def parse_month_half(self, part):
        match = re.match(r"(\d+)(A|B)$", part.strip(), re.IGNORECASE)
        if match:
            month = int(match.group(1))
            half = match.group(2).upper()
            if 1 <= month <= 9:
                return month, half
        return None, None

    # Extract start and destination locations from route line
    def parse_route(self, line):
        match = re.match(r"(.*?)\s+to\s+(.*)", line, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None, None

    # Build a region connection graph for pathfinding
    def build_region_graph(self):
        graph = {}
        for region, connections in region_travel_map.items():
            graph.setdefault(region, set())
            for neighbor in connections["neighbours"]:
                graph[region].add(neighbor)
                graph.setdefault(neighbor, set()).add(region)
        return graph

    # Find the shortest region-to-region path using BFS
    def shortest_path(self, start_region, end_region, graph):
        if start_region == end_region:
            return [start_region]

        visited = set()
        queue = deque([(start_region, [start_region])])

        while queue:
            current, path = queue.popleft()
            if current == end_region:
                return path
            visited.add(current)
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return None  # No valid path found

    # Calculate arrival month/half based on number of regions crossed
    def calculate_arrival(self, path, month, half):
        hops = len(path) - 1  # Number of region-to-region transitions

        if hops == 0:
            # Same region: next half-month
            return (month, "B") if half == "A" else ((month % 9) + 1, "A")

        # Each additional region = +1 month
        month += hops
        while month > 9:
            month -= 9  # Wrap around to 1 after month 9

        return month, half

    # Detect chokepoints in the travel path that require special permissions
    def check_chokepoints_in_path(self, path):
        notices = []

        for i in range(len(path) - 1):
            region_a = path[i]
            region_b = path[i + 1]
            pair = {region_a, region_b}

            if pair == {"Riverlands", "Vale"}:
                notices.append("Movement between the Riverlands and the Vale requires permission to pass through the Bloody Gate. Please ping the controller of the Bloody Gate for permission (presumed House Arryn).")

            if pair == {"Riverlands", "North"}:
                notices.append("Movement between the Riverlands and the North requires permission to pass through Moat Cailin. Please ping the controller of Moat Cailin for permission (presumed House Stark).")

            if pair == {"Riverlands", "Westerlands"}:
                notices.append("Movement between the Riverlands and the Westerlands requires permission to pass through the Golden Tooth. Please ping House Lefford of the Golden Tooth for permission, or their overlord if unclaimed.")

            if pair == {"Stormlands", "Dorne"}:
                notices.append("Movement between the Stormlands and Dorne is assumed to pass through the Boneway or the eastern Prince’s Pass. For the Boneway, both House Dondarrion and House Yronwood must be pinged for permission, or their overlords if unclaimed. For the eastern Prince's Pass. both House Caron and House Fowler must be pinged for permission, or their overlords if unclaimed")

            if pair == {"Reach", "Dorne"}:
                notices.append("Movement between the Reach and Dorne is assumed to pass through the western Prince’s Pass. Both House Tarly and House Dayne must be pinged for permission, or their overlords if unclaimed.")

        return notices

    # Main handler function to process a TP request
    def handle(self):
        print("DEBUG lines:", self.lines)

        month, half, route_line = None, None, None

        # Parse relevant lines from the comment
        for line in self.lines:
            if re.match(r"^\d+(A|B)$", line.strip(), re.IGNORECASE):
                month, half = self.parse_month_half(line)
            elif re.match(r".*\s+to\s+.*", line, re.IGNORECASE):
                route_line = line

        # Validate essential information
        if not month or not half:
            self.comment.reply("Could not find valid departure time. Use format like '4A'. Month 1-9, Half 'A' or 'B'.")
            return

        if not route_line:
            self.comment.reply("Could not find valid route. Use format like 'Location to Location' (e.g., 'Riverrun to King's Landing').")
            return

        start_loc, end_loc = self.parse_route(route_line)
        if not start_loc or not end_loc:
            self.comment.reply("Improperly formatted route. Use format like 'Location to Location' (e.g., 'Riverrun to King's Landing').")
            return

        start_region = location_to_region.get(start_loc)
        end_region = location_to_region.get(end_loc)

        if not start_region or not end_region:
            self.comment.reply(f"Unknown location(s). Check spelling, apostrophes, and capitalization for: {start_loc}, {end_loc}.")
            return

        # Build graph and compute shortest path
        graph = self.build_region_graph()
        path = self.shortest_path(start_region, end_region, graph)

        if not path:
            self.comment.reply("Could not calculate valid travel path. Please check location and destination configuration.")
            return

        # Calculate arrival time based on path
        arrival_month, arrival_half = self.calculate_arrival(path, month, half)

        # Format reply
        reply_text = f"You will arrive in {end_loc} during {arrival_month}{arrival_half}."
        route_summary = " → ".join(path)
        reply_text += f"\n\n**Route Taken:** {route_summary}"

        # Add chokepoint notices if applicable
        notices = self.check_chokepoints_in_path(path)
        if notices:
            reply_text += "\n\n**Note:**\n" + "\n".join(f"\n- {notice}" for notice in notices)

        self.comment.reply(reply_text)


"""Commentary processing logic."""

import random
from typing import Dict, List, Tuple


class CommentaryGenerator:
    """Processes cricket commentary from database or templates."""
    
    # Intensity to excitement level mapping
    INTENSITY_MAP = {
        "low": 2,
        "normal": 5,
        "medium": 7,
        "high": 9,
        "extreme": 10,
    }
    
    # Static commentary dictionary - fallback templates (no LLM)
    TEMPLATES: Dict[int | str, List[str]] = {
        # Wickets
        -1: [
            "HE'S GONE! Bowled him! Absolute timber!",
            "OUT! What a beauty!",
            "WICKET! No doubt about it!",
            "BOWLED!",
            "TAKEN!",
            "TIMBER! The stumps are shattered!",
            "CLEAN BOWLED! What a delivery!",
            "CAUGHT! Straight to the fielder!"
        ],
        # Sixes
        6: [
            "SIX! That's massive! Into the roof!",
            "OH WHAT A SHOT! That's gone all the way!",
            "HUGE! That's outta here! SIX runs!",
            "MONSTER HIT! That's flying into the next bay!",
            "BOOM! That's a maximum! What a strike!",
            "BANG! Six runs! Absolutely smashed!",
            "COLOSSAL! That's sailed into the stands!",
            "MIGHTY HIT! Six all the way!"
        ],
        # Fours
        4: [
            "FOUR! Cracked away! Races to the boundary!",
            "EDGED AND FOUR! Flies past the keeper!",
            "GREAT SHOT! That's a classy boundary!",
            "SMASHED! Four more! Excellent timing!",
            "DRIVEN! Beautifully played for four!",
            "SWEET TIMING! That's racing to the fence!",
            "FOUR RUNS! Perfectly placed!",
            "BOUNDARY! What a shot!"
        ],
        # Threes
        3: [
            "Three runs! Superb running between the wickets!",
            "They steal three! Brilliant effort!",
            "THREE! Excellent placement and running!",
            "Great running! Three runs taken!"
        ],
        # Twos
        2: [
            "Two runs! Excellent placement!",
            "They come back for two! Great hustle!",
            "Pushed for a couple — good cricket!",
            "TWO! Smart running between the wickets!",
            "A couple of runs! Well placed!"
        ],
        # Singles
        1: [
            "Quick single! Good running!",
            "They scamper through for one!",
            "Pushed into the gap — one run.",
            "Nicely played — single taken.",
            "ONE! Rotates the strike!",
            "Single stolen! Quick running!"
        ],
        # Dot balls
        0: [
            "Dot ball. Good tight bowling.",
            "Beaten! Excellent delivery!",
            "No run. Played and missed!",
            "Solid defense. Dot ball.",
            "Swing and a miss! Pressure building!",
            "DOT! Brilliant bowling!",
            "Nothing there! Tight delivery!",
            "Defended! No run!"
        ],
        # Extras (future support)
        "wide": [
            "WIDE! Way down the leg side!",
            "That's a wide — bonus run!",
            "Too wide! Extras on the board.",
            "WIDE BALL! Poor delivery!"
        ],
        "no_ball": [
            "NO BALL! Free hit coming up!",
            "Overstepped! That's a no ball!",
            "NO BALL! And it's been hit hard!",
            "NO BALL! Extra run and a free hit!"
        ],
        "bye": [
            "Byes! The keeper couldn't stop it!",
            "Missed by everyone — byes!",
            "That sneaks past — extra runs!",
            "BYES! Goes through to the boundary!"
        ],
        "leg_bye": [
            "Leg byes! Off the pads!",
            "Struck on the pad — leg byes!",
            "LEG BYE! Hit the pad!",
            "Off the pads! Leg bye!"
        ]
    }
    
    def __init__(self):
        """Initialize the commentary generator."""
        pass
    
    def get_from_database(self, ball_event: Dict) -> Tuple[str, int]:
        """
        Extract commentary from database sentence field.
        
        Args:
            ball_event: Dictionary containing 'sentence' and 'intensity' fields
            
        Returns:
            Tuple of (commentary_text, excitement_level)
            excitement_level: 0-10, where 10 is most excited
        """
        # Get sentence from database
        sentence = ball_event.get("sentence", "").strip()
        
        # Get intensity and map to excitement level
        intensity = ball_event.get("intensity", "normal").lower().strip()
        excitement = self.INTENSITY_MAP.get(intensity, 5)
        
        # If no sentence provided, fallback to template generation
        if not sentence:
            return self._generate_from_template(ball_event)
        
        return sentence, excitement
    
    def _generate_from_template(self, ball_event: Dict) -> Tuple[str, int]:
        """
        Fallback: Generate commentary from templates when database sentence is empty.
        
        Args:
            ball_event: Dictionary containing runs_scored and optional extra_type
            
        Returns:
            Tuple of (commentary_text, excitement_level)
        """
        runs = ball_event.get("runs_scored", 0)
        extra_type = ball_event.get("extra_type", "").lower() if "extra_type" in ball_event else ""
        
        # Priority: Wicket first
        if runs == -1:
            return random.choice(self.TEMPLATES[-1]), 10
        
        # Extras (for future extra_type column support)
        if extra_type and extra_type in self.TEMPLATES:
            return random.choice(self.TEMPLATES[extra_type]), 5
        
        # Runs with excitement levels
        if runs >= 6:
            return random.choice(self.TEMPLATES[6]), 10
        elif runs == 4:
            return random.choice(self.TEMPLATES[4]), 7
        elif runs == 3:
            return random.choice(self.TEMPLATES[3]), 5
        elif runs == 2:
            return random.choice(self.TEMPLATES[2]), 3
        elif runs == 1:
            return random.choice(self.TEMPLATES[1]), 2
        else:
            return random.choice(self.TEMPLATES[0]), 1
    
    def generate(self, ball_event: Dict) -> Tuple[str, int]:
        """
        Generate commentary for a ball event (uses database sentence if available).
        
        Args:
            ball_event: Dictionary containing database fields (sentence, intensity, runs_scored, etc.)
            
        Returns:
            Tuple of (commentary_text, excitement_level)
            excitement_level: 0-10, where 10 is most excited
        """
        # Primary: Use database sentence
        return self.get_from_database(ball_event)
    
    def generate_welcome(self, team_one: str, team_two: str) -> tuple[str, int]:
        """Generate match welcome announcement."""
        text = (
            f"Ladies and gentlemen, welcome to this exciting indoor cricket match between "
            f"{team_one} and {team_two}! Here we go!"
        )
        return text, 9
    
    def generate_innings_break(self) -> tuple[str, int]:
        """Generate innings break announcement."""
        return "That's the end of the first innings! Time for a short break.", 4
    
    def generate_match_end(self, winner: str) -> tuple[str, int]:
        """Generate match end announcement."""
        if not winner or winner == "Draw":
            text = "And that's the game! It's a thrilling draw! What a contest!"
        else:
            text = f"And that's the game! {winner} wins this thrilling contest! What a match!"
        return text, 10

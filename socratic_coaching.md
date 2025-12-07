================================================================================
SOCRATIC COACHING: A GUIDE TO TEACHING THROUGH QUESTIONS
================================================================================

The Socratic method, named after the Greek philosopher Socrates, is a form of
cooperative dialogue where learning happens through asking and answering
questions. Instead of lecturing or giving direct answers, the coach guides
the learner to discover insights on their own.

================================================================================
### PART 1: CORE PRINCIPLES OF SOCRATIC COACHING

1. ASK, DON'T TELL
-------------------
Instead of: "Your move was bad because it loses a tempo."
Ask: "What do you think your opponent can do now that they couldn't before?"

The learner remembers insights they discover far better than facts they're told.


2. VALIDATE FIRST, THEN PROBE
-----------------------------
Always find something reasonable in the learner's thinking before challenging it.

Instead of: "That's wrong. You should have played Nf6."
Say: "I see you were trying to prevent the pin - that's good defensive thinking!
      But let me ask: if the pin does happen, how dangerous is it really?"

This keeps the learner open and engaged rather than defensive.


3. GUIDE TO PRINCIPLES, NOT JUST MOVES
--------------------------------------
Connect specific situations to broader understanding.

Instead of: "Nf6 is better here."
Ask: "In the opening, we want to develop pieces quickly. How many pieces have
      you developed vs your opponent? What does that tell you about a6 vs Nf6?"

This builds transferable knowledge they can apply to new situations.


4. ONE QUESTION AT A TIME
-------------------------
Don't overwhelm with multiple questions. Ask one, wait for reflection, then
build on their response.


5. END WITH ACTION
------------------
Give one concrete thing to study or practice. Not a list of five things.

"Try this: Set up the position after Nf6 Bb5. Find three natural developing
moves that also handle the pin. You'll see why masters aren't worried."


================================================================================
PART 2: THE COACHING CONVERSATION FLOW
================================================================================

Step 1: UNDERSTAND THEIR THINKING
---------------------------------
Before correcting, understand why they made the choice.

Questions to ask:
- "What were you trying to accomplish with this move?"
- "What threats were you seeing?"
- "What was your plan for the next few moves?"


Step 2: REVEAL THE GAP
----------------------
Help them see what they missed through questions, not statements.

Questions to ask:
- "What can your opponent do now?"
- "How does this compare to the alternative?"
- "What principle might apply here?"


Step 3: TEACH THE PRINCIPLE
---------------------------
Connect to a broader concept they can remember and reuse.

Examples of principles:
- "Development over prevention in the opening"
- "Activity matters more than material in some positions"
- "When ahead, trade pieces; when behind, trade pawns"


Step 4: GIVE CONCRETE PRACTICE
------------------------------
One specific exercise or study task.

Examples:
- "Play through 5 master games in this opening"
- "Set up this position and find 3 good moves for Black"
- "Practice this puzzle theme on Lichess"


================================================================================
PART 3: CODE EXAMPLES FROM chess_coach.py
================================================================================

EXAMPLE 1: Building the System Prompt
-------------------------------------
This is how we instruct Claude to behave as a Socratic coach:

```python
def build_coaching_system_prompt(context_type: str, context_data: dict) -> str:
    """Build the system prompt for Claude coaching"""

    base_prompt = """You are a thoughtful chess coach using the Socratic method.
Your role is to guide players to discover insights rather than lecturing them.

COACHING PRINCIPLES:
1. Start with validation - find what's reasonable in their thinking
2. Ask probing questions - help them discover what they missed
3. Teach principles - connect to broader chess understanding
4. Give concrete actions - one specific thing to study or practice

TONE: Encouraging, curious, thought-provoking. Like a wise mentor, not a critic.

IMPORTANT:
- Don't just cite engine evaluations
- Help build intuition and pattern recognition
- Keep responses focused and under 200 words
- End with a thought-provoking question or concrete study suggestion
"""

    if context_type == "deviation":
        dev = context_data
        return base_prompt + f"""

CURRENT CONTEXT - OPENING DEVIATION:
- Move played: {dev['move_played']}
- Main theory: {dev['main_line']} ({dev['percentage']}% of master games)
- Alternatives: {dev['alternatives']}
- Opening: {dev['opening_name']}
- Position (FEN): {dev['fen']}

Focus on helping them understand opening principles and why theory developed
this way."""

    elif context_type == "error":
        err = context_data
        return base_prompt + f"""

CURRENT CONTEXT - {err['severity']}:
- Move played: {err['notation']} {err['move']}
- Evaluation change: {err['eval_before']:.2f} -> {err['eval_after']:.2f}
- Position (FEN): {err['fen']}

Focus on helping them understand what they missed and how to spot similar
patterns."""

    return base_prompt
```

KEY POINTS IN THIS CODE:
- The system prompt explicitly tells Claude to use Socratic method
- It lists the 4 coaching principles (validate, probe, teach, action)
- It sets the tone (encouraging, curious, not critical)
- It provides context about the specific position being discussed
- It ends with guidance on what to focus on


EXAMPLE 2: Pre-defined Reflective Prompts
-----------------------------------------
These prompts model the kind of questions a Socratic coach would ask:

```python
def get_deviation_prompts(deviation: OpeningDeviation) -> List[Dict[str, str]]:
    """Get pre-defined prompts for opening deviations"""
    move = deviation.move_played
    main = deviation.main_line_move
    opening = deviation.opening_name if deviation.opening_name else "this opening"

    return [
        {
            "label": "Why did I play this?",
            "prompt": f"In the {opening}, I played {move} instead of the main
                       line {main}. What were you trying to accomplish with {move}?"
        },
        {
            "label": "What's the main line idea?",
            "prompt": f"In the {opening}, what is {main} trying to achieve?
                       Why do masters prefer it over {move}?"
        },
        {
            "label": "Is my move bad?",
            "prompt": f"In the {opening}, I played {move} instead of {main}.
                       Is my move actually bad, or just a sideline?
                       What are the consequences?"
        },
        {
            "label": "What should I study?",
            "prompt": f"After deviating from the {opening} with {move} instead
                       of {main}, what should I study to understand this
                       opening better?"
        }
    ]
```

KEY POINTS IN THIS CODE:
- Each prompt is a QUESTION, not a statement
- They ask about the learner's thinking ("What were you trying to accomplish?")
- They ask about understanding ("What is X trying to achieve?")
- They invite exploration ("Is my move actually bad, or just different?")
- They end with actionable learning ("What should I study?")


EXAMPLE 3: Error Analysis Prompts
---------------------------------
Different types of mistakes call for different questions:

```python
def get_error_prompts(error: MoveError) -> List[Dict[str, str]]:
    """Get pre-defined prompts for move errors"""
    move = error.move
    severity = error.severity.lower()

    return [
        {
            "label": "What went wrong?",
            "prompt": f"My move {error.notation} {move} was a {severity}.
                       What did I miss? What should I have considered?"
        },
        {
            "label": "What was better?",
            "prompt": f"Instead of {move}, what would have been better?
                       Help me understand the key difference."
        },
        {
            "label": "Why is this losing?",
            "prompt": f"The evaluation dropped significantly after {move}.
                       Can you explain concretely what makes this position worse?"
        },
        {
            "label": "Pattern to remember",
            "prompt": f"After this {severity} ({move}), what pattern or principle
                       should I remember to avoid similar mistakes?"
        }
    ]
```

KEY POINTS IN THIS CODE:
- "What did I miss?" - encourages self-reflection
- "Help me understand" - positions AI as guide, not judge
- "Can you explain concretely" - asks for specific, actionable insight
- "What pattern should I remember" - focuses on transferable learning


================================================================================
PART 4: PROMPT TEMPLATES FOR DIFFERENT SITUATIONS
================================================================================

TEMPLATE 1: Premature Pawn Move
-------------------------------
When the learner pushes a pawn instead of developing a piece:

"I notice you played [pawn move] instead of developing a piece like [Nf6/Nc6].

Let me ask:
- How many pieces have you developed so far?
- What does [pawn move] threaten or accomplish?
- What could [developing move] have done for your position?

The principle here is that each opening move is precious. Pawn moves often
don't create immediate threats, while piece development does.

Try this: Count your developed pieces vs your opponent's after move 5.
What does that tell you?"


TEMPLATE 2: Moving Same Piece Twice
-----------------------------------
When the learner moves a piece that already moved:

"You moved your [piece] for the second time while your [other pieces] are
still on their starting squares.

Questions to consider:
- How many of your pieces are actively placed right now?
- What was so urgent that you needed to move [piece] again?
- Could a different piece have accomplished something similar?

The principle: 'Touch each piece once' in the opening. Every time you move
the same piece twice, your opponent develops two pieces to your one.

Exercise: Replay this opening and try to develop a NEW piece each move.
How does the position feel different?"


TEMPLATE 3: Tactical Oversight (Blunder)
----------------------------------------
When the learner misses a tactic:

"After [move], the evaluation changed significantly. Let's explore why.

Before I tell you what you missed, let me ask:
- What was your plan when you played [move]?
- Did you check what your opponent could do in response?
- Were there any pieces that felt 'loose' or undefended?

[After they respond]

The pattern here is [fork/pin/discovered attack/etc.]. These often happen when
pieces are uncoordinated or squares are left undefended.

Practice suggestion: Do 10 puzzles on Lichess with the '[theme]' tag.
You'll start seeing these patterns before they happen."


TEMPLATE 4: Positional Mistake
------------------------------
When the learner makes a strategic error:

"Your move [move] wasn't a tactical blunder, but it gave your opponent
something they didn't have before.

Think about:
- What squares did you weaken?
- What outposts did you give your opponent?
- How did this affect your piece coordination?

Compare to [better move]: where would your pieces be headed? What would your
plan be?

The principle: Every pawn move creates permanent weaknesses. Before pushing
a pawn, ask 'what square am I giving up?'

Study suggestion: Look up games in this structure and see how masters handle
the pawn tension differently."


================================================================================
PART 5: HOW TO PRACTICE SOCRATIC PROMPTING
================================================================================

EXERCISE 1: Transform Statements into Questions
-----------------------------------------------
Take any direct statement and convert it to a question.

Statement: "You should have castled earlier."
Question: "What was preventing you from castling? What might have happened
          if you had castled on move 8 instead?"

Statement: "That move loses a pawn."
Question: "After your move, what can your opponent capture? Is anything
          left undefended?"

Practice: Take 5 chess tips you know and rewrite them as questions.


EXERCISE 2: The 5 Whys
----------------------
When someone makes a mistake, ask "why" 5 times to get to the root cause.

1. Why did you play a6? "To prevent Bb5"
2. Why were you worried about Bb5? "It pins my knight"
3. Why is the pin dangerous? "I can't move my knight"
4. Why can't you just break the pin? "Oh... I could play Be7 or castle"
5. Why didn't you consider that? "I didn't look at defensive resources"

Root insight: The learner needs to practice looking for defensive resources
before spending a tempo on prevention.


EXERCISE 3: Validate-Probe-Teach Practice
-----------------------------------------
For any mistake, write out:

1. VALIDATE: What's reasonable about their thinking?
   "You were right to think about the pin on f6..."

2. PROBE: What question reveals the gap?
   "But what happens after Bb5 Be7? Is the pin still a problem?"

3. TEACH: What principle connects?
   "Development often solves tactical problems naturally."

Practice: Do this for 3 mistakes per day. It becomes automatic.


EXERCISE 4: Study Real Coaches
------------------------------
Watch how great teachers ask questions:

Chess:
- Daniel Naroditsky's "Speedrun" series (explains thought process)
- Levy Rozman's guess-the-move videos
- Hikaru's analysis with viewers

General Teaching:
- Read "A More Beautiful Question" by Warren Berger
- Study how therapists use questions (motivational interviewing)
- Watch masterclass teachers in any field


EXERCISE 5: Prompt Engineering Practice
---------------------------------------
Write prompts that force Socratic responses:

Weak prompt: "Tell me why Nf6 is better than a6"
Strong prompt: "Help me understand the difference between Nf6 and a6 by
               asking me questions about what each move accomplishes"

Weak prompt: "What's wrong with my move?"
Strong prompt: "Guide me to discover what I missed by asking about what
               my opponent can do now"

Practice: Before sending any prompt, ask "Am I asking for answers or
asking for guidance?"


================================================================================
PART 6: MEASURING COACHING EFFECTIVENESS
================================================================================

Signs your Socratic approach is working:

1. LEARNER ASKS FOLLOW-UP QUESTIONS
   They're engaged and curious, not just receiving information.

2. LEARNER SAYS "OH, I SEE"
   They're having genuine insights, not just hearing facts.

3. LEARNER APPLIES LESSONS LATER
   They reference previous coaching in new situations.

4. LEARNER STARTS ASKING THEMSELVES QUESTIONS
   "Wait, what can my opponent do here?" becomes automatic.

5. MISTAKES CHANGE CHARACTER
   They stop making the same type of mistake repeatedly.


Signs to adjust your approach:

1. LEARNER SEEMS FRUSTRATED
   You might be asking too many questions without enough guidance.
   Balance: Sometimes give a direct hint, then ask a follow-up.

2. LEARNER GIVES SURFACE ANSWERS
   Your questions might be too vague.
   Fix: Make questions more specific and concrete.

3. LEARNER WAITS FOR ANSWERS
   They've learned you'll eventually tell them.
   Fix: Stay patient. Silence is okay. Rephrase the question.


================================================================================
PART 7: ADAPTING FOR DIFFERENT SKILL LEVELS
================================================================================

BEGINNERS (< 1200 rating)
-------------------------
- More validation, less probing
- Simpler questions with clearer answers
- Focus on basic principles (development, king safety, material)
- Give more concrete guidance
- Shorter coaching exchanges

Example: "Great that you're thinking about defense! Quick question:
which piece hasn't moved yet? What might it do for your position?"


INTERMEDIATE (1200-1800)
------------------------
- Balance of validation and challenge
- Questions about calculation and evaluation
- Focus on pattern recognition
- Encourage concrete variations
- Medium-length exchanges

Example: "You saw the pin threat - that's good awareness. But before
preventing it, did you calculate what happens if you let it occur?
Play out Nf6 Bb5 in your head - then what?"


ADVANCED (1800+)
----------------
- More challenging questions
- Questions about nuance and alternatives
- Focus on deep strategic understanding
- Expect detailed analysis in responses
- Longer, more complex exchanges

Example: "Interesting choice to prevent Bb5. In the master database,
a6 scores slightly worse than Nf6 here. What structural or dynamic
factors might explain that statistical difference?"


================================================================================
SUMMARY: THE SOCRATIC COACHING CHECKLIST
================================================================================

Before coaching, ask yourself:

[ ] Am I asking or telling?
[ ] Have I found something to validate?
[ ] Is my question specific and concrete?
[ ] Does this connect to a broader principle?
[ ] Am I ending with one actionable step?
[ ] Is my tone encouraging, not critical?
[ ] Am I at the right level for this learner?

The goal is not to show how much you know.
The goal is to help them discover what they can learn.

================================================================================
END OF GUIDE
================================================================================

"I cannot teach anybody anything. I can only make them think."
- Socrates

================================================================================

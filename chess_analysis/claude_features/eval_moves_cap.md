```bash

> great for another UI improvement can you Evaluating move 7/51
 cap it at 20 .. /# because the API works only for the initial moves please 

⏺ Read(chess_coach.py)
  ⎿  Read 60 lines

⏺ Update(chess_coach.py)
  ⎿  Updated chess_coach.py with 8 additions and 5 removals              
       446            elif not book_data or not book_data['moves']:
       447                left_book = True
       448    
       449 -      # Phase 2: Evaluate all positions
       449 +      # Phase 2: Evaluate positions (cap at 20 moves - 
           + Lichess cloud eval works best for common positions)
       450 +      MAX_EVAL_MOVES = 20
       451 +      moves_to_eval = min(len(moves), MAX_EVAL_MOVES)
       452 +  
       453        if progress_callback:
       454            progress_callback(0, "Evaluating positions...")
       455    
     ...
       457        eval_result = get_lichess_cloud_eval(board.fen())
       458        evaluations.append(eval_result['score'] if eval_result 
             else 0)
       459    
       460 -      for i, move in enumerate(moves):
       460 +      for i, move in enumerate(moves[:moves_to_eval]):
       461            board.push(move)
       462            eval_result = get_lichess_cloud_eval(board.fen())
       463            evaluations.append(eval_result['score'] if 
             eval_result else evaluations[-1])
       464    
       465            if progress_callback:
       466 -              progress_callback((i + 1) / total_moves
           -  , f"Evaluating move {i + 1}/{total_moves}")
       466 +              progress_callback((i + 1) / moves_to_eval
           +  , f"Evaluating move {i + 1}/{moves_to_eval}")
       467    
       468            # Small delay to be nice to Lichess API
       469            time.sleep(0.1)
       470    
       471 -      # Phase 3: Find mistakes
       471 +      # Phase 3: Find mistakes (only for evaluated moves)
       472        board.reset()
       473        move_errors = []
       474    
       475 -      for i, move in enumerate(moves):
       475 +      for i, move in enumerate(moves[:moves_to_eval]):
       476            move_san = board.san(move)
       477            move_num = i // 2 + 1
       478            is_white = i % 2 == 0



```

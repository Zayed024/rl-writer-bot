import os
import chromadb
import datetime
import uuid
import asyncio
from gtts import gTTS
import vlc
import time 

import Levenshtein

import review, spin_write,scrape, prompt_generator, prompt_manager

url_to_scrape = "https://en.wikisource.org/wiki/The_Gates_of_Morning/Book_1/Chapter_1"

spin_write_instance = spin_write.SpinWrite()
review_instance = review.Review()
prompt_gen_instance = prompt_generator.PromptGenerator()

sw_model= spin_write_instance.model_name
r_model= review_instance.model_name
pg_model = prompt_gen_instance.model_name

DEFAULT_BOOK_NAME_SLUG = "The_Gates_of_Morning"
book_name, book_num, chap_num=scrape.book_chapter_info(url_to_scrape)
#set path to chroma data directory
CHROMA_DB_PATH="main/chroma_data"
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

collection = client.get_or_create_collection(name="data")
print(f"ChromaDB initialized at: {CHROMA_DB_PATH}") 


#reward calculation
def calculate_reward(action_choice: str, 
                     original_len: int, 
                     edited_len: int, 
                     iteration_count: int,
                     human_rating: int = None,  
                     lev_distance_ratio: float = None) -> float:
    """
    Calculates a reward based on human action, edit extent (Levenshtein),
    and a direct human rating.

    Args:
        action_choice (str): The choice made by the human (1, 2, 3).
        original_len (int): Length of the AI-spun content before human edit.
        edited_len (int): Length of the content after human edit.
        iteration_count (int): How many times this chapter has been iterated.
        human_rating (int, optional): A 1-5 star rating provided by the human.
        lev_distance_ratio (float, optional): Normalized Levenshtein distance (0-1), 0 for no change.

    Returns:
        float: A numerical reward value.
    """
    reward = 0.0

    if action_choice == '2': # Accept current content and finalize
        # High positive reward for final acceptance
        reward = 10.0
    if lev_distance_ratio is not None:
        # Deduct if significant edits were made before finalization
        # A higher lev_distance_ratio means more changes, so higher deduction
        reward -= (lev_distance_ratio * 5.0) # Deduct up to 5 points based on edit extent
        print(f" Levenshtein deduction: {(lev_distance_ratio * 5.0):.2f}")


    elif action_choice == '1': # Edit directly
        reward = 3.0 # Starting with a small positive base
        if lev_distance_ratio is not None:
            # Reward is higher if less change, negative if extensive change
            #0 change = 3 points; 10% change = 3 - 1 = 2; 50% change = 3 - 5 = -2
            reward -= (lev_distance_ratio * 10.0)
            print(f"  - Levenshtein impact: {(lev_distance_ratio * -10.0):.2f}")
        reward = max(reward, -5.0) #min cap

    elif action_choice == '3': # Request AI to re-spin
        reward = -5.0 # Negative reward, as previous AI spin was not good enough

    # Incorporating human rating if provided
    if human_rating is not None:
        rating_impact = (human_rating - 3) * 2.0 # (1->-4, 2->-2, 3->0, 4->2, 5->4)
        reward += rating_impact
        print(f"  - Human rating impact: {rating_impact:.2f} (Rating: {human_rating})")

    # Penalize for more iterations (implies AI isn't learning fast enough)
    iteration_penalty = iteration_count * 0.1
    final_reward = reward - iteration_penalty
    print(f"  - Iteration penalty: -{iteration_penalty:.2f}")

    return final_reward


def speak_text(text, filename="output.mp3"):
    """
    Generates speech from text and plays it using VLC.
    Requires gTTS and python-vlc to be installed, and VLC Media Player on the system.
    """
    try:
        if not text.strip():
            print("No text to speak.")
            return

        print(f"Generating speech for: '{text[:50]}...'")
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(filename)

        player_instance = vlc.Instance()
        player = player_instance.media_player_new()

        media = player_instance.media_new(filename)
        player.set_media(media)
        player.play()
        while True:
            state = player.get_state()
            if state == vlc.State.Ended or state == vlc.State.Stopped or state == vlc.State.Error:
                break
            time.sleep(0.1)
        print("Playback finished.")
        
        os.remove(filename)
    except Exception as e:
        print(f"Error speaking text: {e}")
        print("Please Ensure VLC Media Player is installed and accessible to python-vlc")

def load_content(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None


async def scrape_new(chroma_collection):
    """
    Prompts user for new chapter/book details and scrapes it 
    and initiates HITL worklow if valid
    """
    print("\n Scrape New Chapter")
    print(f"Current default book: '{DEFAULT_BOOK_NAME_SLUG.replace('_',' ')}'")
    book_name_input = input("Enter Book Title or leave blank for default: ").strip()
    book_name_slug = book_name_input.replace(' ', '_') if book_name_input else DEFAULT_BOOK_NAME_SLUG

    while True:
        try:
            book_num_input = int(input("enter book number: "))
            chap_num_input = int(input("Enter chapter number: "))
            break
        except ValueError:
            print("Invalid number. Please Enter integers")

    scraped_content,page_title,screenshot_path,is_valid =await scrape.scrape_content(
        book_name_slug,book_num_input,chap_num_input
    )        

    if not is_valid:
        print("Invalid chapter or book number.")
        print("The requested chapter or book could not be found or has no content")
        print("Check the numbers and book title and try again")
        return
    
    print("Chapter Scraped successfully! ")
    print(f"Title: {page_title}")
    print(f"Saved to: scraped_content_{book_name_slug}_Book{book_num_input}_Chapter{chap_num_input}.txt")

    print("\n Generating initial AI spin and review for new chapter")
    spun_content_for_init,initial_prompt_name = await spin_write_instance.ai_spin_content(scraped_content,None)
    review_comments_for_init = await review_instance.ai_review_content(spun_content_for_init)

    new_chapter_spun_file = f"spun_content_{book_name_slug}_Book{book_name_slug}_Chapter{chap_num_input}.txt"
    new_chapter_review_file = f"reviewer_comments_{book_name_slug}_Book{book_name_slug}_Chapter{chap_num_input}.txt"

    with open(new_chapter_spun_file,'w',encoding='utf-8') as f:
        f.write(spun_content_for_init)
    with open(new_chapter_review_file,'w',encoding='utf-8') as f:
        f.write(review_comments_for_init)

    print(f"initial spin used prompt:\n {initial_prompt_name}")

    await human_in_the_loop_workflow(
        original_content_path=f"scraped_content_{book_name_slug}_Book{book_num_input}_Chapter{chap_num_input}.txt",
        initial_spun_content_path=new_chapter_spun_file,
        initial_review_comments_path=new_chapter_review_file,
        book_title=book_name_slug.replace('_',' '),
        book_num= book_num_input,
        chapter_num=chap_num_input,
        chroma_collection=chroma_collection,
        current_version_num=1,
        prompt_used_for_current_spin_on_start=initial_prompt_name,
        original_chapter_content=scraped_content

    )
            
    print(f"\nFinished workflow for {book_name_slug.replace('_', ' ')} Book {book_num_input} Chapter {chap_num_input} ")

async def human_in_the_loop_workflow(
    
    original_content_path: str,
    initial_spun_content_path: str,
    initial_review_comments_path: str,
    current_version_num: int = 1,
    book_title: str = book_name,
    book_num: int=book_num,
    chapter_num: int = chap_num,
    chroma_collection= None,
    prompt_used_for_current_spin_on_start: str = "unknown_initial_prompt",
    original_chapter_content: str = ""
    
):
    print("\nStarting Human-in-the-Loop process")

    if chroma_collection is None:
        print("Error: ChromaDB collection not provided. Exiting.")
        return

    chapter_base_id = f"{book_title.replace(' ', '_')}_Book{book_num}_Chapter{chapter_num}"


   # Load and add ORIGINAL content to ChromaDB (if not already there)
    original_content = load_content(original_content_path)
    if original_content is None: return

     # Check if original is already added to avoid duplicates on restart
    results = chroma_collection.get(ids=[f"{chapter_base_id}_v0_original"])
    if not results['ids']:
        chroma_collection.add(
                documents=[original_content],
                metadatas=[{
                    "book_title": book_title,
                    "book_num": book_num,
                    "chapter_num": chapter_num,
                    "version": 0, # 0 for original content
                    "type": "original",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "source_file": original_content_path
                }],
                ids=[f"{chapter_base_id}_v0_original"]
        )

        print(f"Original content added to ChromaDB: {chapter_base_id}_v0_original")
    else:
        print(f"Original content already exists in ChromaDB: {chapter_base_id}_v0_original")
    
    spun_content_current = load_content(initial_spun_content_path)
    if spun_content_current is None: return

    review_comments_current = load_content(initial_review_comments_path)
    if review_comments_current is None: return

    prompt_used_for_current_spin = prompt_used_for_current_spin_on_start
    
    results = chroma_collection.get(ids=[f"{chapter_base_id}_v{current_version_num}_ai_spin"])
    if not results['ids']:
        chroma_collection.add(
            documents=[spun_content_current],
            metadatas=[{
                "book_title": book_title,
                "book_num": book_num,
                "chapter_num": chapter_num,
                "version": current_version_num,
                "type": "ai_spin",
                "timestamp": datetime.datetime.now().isoformat(),
                "model_used": sw_model,
                "prompt_template_name": prompt_used_for_current_spin_on_start
            }],
            ids=[f"{chapter_base_id}_v{current_version_num}_ai_spin"]
        )
        print(f"Initial AI-spun content added to ChromaDB: {chapter_base_id}_v{current_version_num}_ai_spin")

    else: # If the initial spin IS in ChromaDB, retrieve its prompt name
        print(f"Initial AI-spun content already exists in ChromaDB: {chapter_base_id}_v{current_version_num}_ai_spin")
        
        retrieved_metadata = results['metadatas'][0]
        if 'prompt_template_name' in retrieved_metadata:
            prompt_used_for_current_spin = retrieved_metadata['prompt_template_name']
            print(f"  Retrieved prompt for initial spin: '{prompt_used_for_current_spin}'")
        else:
            print("  Warning: Could not retrieve prompt_template_name for existing initial spin. Using 'unknown_initial_prompt'.")
            prompt_used_for_current_spin = "unknown_initial_prompt"    
    
    results = chroma_collection.get(ids=[f"{chapter_base_id}_v{current_version_num}_ai_review"])
    if not results['ids']:
        chroma_collection.add(
            documents=[review_comments_current],
            metadatas=[{
                "book_title": book_title,
                "book_num": book_num,
                "chapter_num": chapter_num,
                "version": current_version_num,
                "type": "ai_review",
                "timestamp": datetime.datetime.now().isoformat(),
                "model_used": r_model, 
                "reviewed_version_id": f"{chapter_base_id}_v{current_version_num}_ai_spin"
            }],
            ids=[f"{chapter_base_id}_v{current_version_num}_ai_review"]
        )
        print(f"Initial AI-review comments added to ChromaDB: {chapter_base_id}_v{current_version_num}_ai_review")

    current_editable_content = spun_content_current
    #prev_content_length = len(current_editable_content)
    previous_content_for_edit_check = current_editable_content

    chapter_summary_for_prompt_gen = await spin_write_instance.ai_summarize(original_chapter_content)

    while True:
        
        name=input("\nplease enter your name:")
        if not name.strip():
            print("Name cannot be empty. Please enter a valid name.")
            continue
        break

    iteration_count = 0

    while True:
        iteration_count+=1

        print(f"\nChapter Review (Book: {book_name}, Chapter: {chapter_num}, Current Version: {current_version_num}, Editor: {name})")
        print("\nOriginal Content (for reference)")
        original_from_db = chroma_collection.get(ids=[f"{chapter_base_id}_v0_original"])['documents'][0]
        print(original_from_db[:500] + "..." if len(original_from_db) > 500 else original_from_db)

        print("\n AI-Spun Content (Current Working Version)")
        print(current_editable_content[:1000] + "..." if len(current_editable_content) > 1000 else current_editable_content)

        print("\nAI Reviewer Comments ")
        print(review_comments_current)

        human_rating_input = None
        while True:
            rating_str = input("Please rate the AI's current spun content (1-5 stars, 5 being excellent, or leave blank): ").strip()
            if not rating_str:
                print("No rating provided.")
                break 
            try:
                rating = int(rating_str)
                if 1 <= rating <= 5:
                    human_rating_input = rating
                    break
                else:
                    print("Rating must be between 1 and 5.")
            except ValueError:
                print("Invalid input. Please enter a number between 1 and 5.")

        print("\nWhat would you like to do?")
        print("1. Edit the current content directly (will open in editor).")
        print("2. Accept current content and finalize.")
        print("3. Request AI to re-spin the chapter with new instructions.")
        print("4. Perform a semantic search on stored chapter versions.") 
        print("5. **Listen to current AI-spun content.**") 
        print("6. **Listen to AI Reviewer Comments.**") 
        print("7. Exit review process.")  

        choice = input("Enter your choice (1-7): ")

        if choice == '1':
            # Option 1: Edit directly. Saving current content to a temp file, open editor, then load back.
            temp_edit_file = "temp_edit.txt"
            with open(temp_edit_file, 'w', encoding='utf-8') as f:
                f.write(current_editable_content)
            print(f"Opening editor for: {temp_edit_file}. Save and close the file when done.")
            if os.name == 'nt': # Windows
                os.system(f"notepad.exe {temp_edit_file}")
            else: # Unix-like (Linux, macOS)
                
                os.system(f"vim {temp_edit_file}")
            
            input("Press Enter when you have finished editing and saved the file in your text editor...")
            edited_content = load_content(temp_edit_file)
            os.remove(temp_edit_file) 
            if edited_content:
                lev_dist = Levenshtein.distance(previous_content_for_edit_check, edited_content)
                max_len = max(len(previous_content_for_edit_check), len(edited_content))
                lev_ratio = lev_dist / max_len if max_len > 0 else 0.0 # Normalize 0-1

                print(f"Levenshtein Distance: {lev_dist} (Normalized Ratio: {lev_ratio:.4f})")

                
                reward_value = calculate_reward(
                    action_choice=choice,
                    original_len=len(previous_content_for_edit_check), # Length before human edit
                    edited_len=len(edited_content),
                    iteration_count=iteration_count,
                    human_rating=human_rating_input,
                    lev_distance_ratio=lev_ratio
                )
                print(f"Calculated Reward for 'Edit': {reward_value:.2f}")

                if prompt_used_for_current_spin not in ["custom_instruction_override", "fallback_default", "unknown_initial_prompt"]:
                    prompt_manager.update_prompt_score(
                        prompt_name=prompt_used_for_current_spin,
                        reward=reward_value,
                        current_scores=spin_write_instance.prompt_scores
                    )
                    spin_write_instance.save_current_prompt_scores()

                current_version_num += 1
                current_editable_content = edited_content 
                previous_content_for_edit_check = current_editable_content
                
                chroma_collection.add(
                    documents=[edited_content],
                    metadatas=[{
                        "book_title": book_title,
                        "book_num": book_num,
                        "chapter_num": chapter_num,
                        "version": current_version_num,
                        "type": "human_edit",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "editor": name,
                        "reward" :reward_value,
                        "levenshtein_ratio": lev_ratio, 
                        "human_rating": human_rating_input if human_rating_input is not None else "Not Rated",
                        "prompt_used_for_spin_before_edit": prompt_used_for_current_spin
                    }],
                    ids=[f"{chapter_base_id}_v{current_version_num}_human_edit"]
                )
                print(f"Human-edited content added to ChromaDB: {chapter_base_id}_v{current_version_num}_human_edit")
                
                print("\nRe-running AI Reviewer on Human-Edited Content")
                review_comments_current = await review_instance.ai_review_content(current_editable_content) 
                print("\nNew AI Reviewer Comments")
                print(review_comments_current)
                
                chroma_collection.add(
                    documents=[review_comments_current],
                    metadatas=[{
                        "book_title": book_title,
                        "book_num": book_num,
                        "chapter_num": chapter_num,
                        "version": current_version_num,
                        "type": "ai_review_after_human",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "model_used": r_model,
                        "reviewed_version_id":f"{chapter_base_id}_v{current_version_num}_human_edit"
                    }],
                    ids=[f"{chapter_base_id}_v{current_version_num}_ai_review_after_human"]
                )
                print(f"New AI review comments after human edit added to ChromaDB: f{chapter_base_id}_v{current_version_num}_ai_review_after_human")
            else:
                print("No content loaded after edit. Retaining previous version.")
            
        elif choice == '2':
            lev_ratio_on_finalize = 0.0 
            if previous_content_for_edit_check != current_editable_content: # If prior edits happened
                lev_dist = Levenshtein.distance(previous_content_for_edit_check, current_editable_content)
                max_len = max(len(previous_content_for_edit_check), len(current_editable_content))
                lev_ratio_on_finalize = lev_dist / max_len if max_len > 0 else 0.0
            reward_value = calculate_reward(
                action_choice=choice,
                original_len=len(previous_content_for_edit_check),
                edited_len=len(current_editable_content),
                iteration_count=iteration_count,
                human_rating=human_rating_input,
                lev_distance_ratio=lev_ratio_on_finalize 
            )
            print(f"Calculated Reward for 'Finalize': {reward_value:.2f}")

            if prompt_used_for_current_spin not in ["custom_instruction_override", "fallback_default", "unknown_initial_prompt"]:
                prompt_manager.update_prompt_score(
                    prompt_name=prompt_used_for_current_spin,
                    reward=reward_value,
                    current_scores=spin_write_instance.prompt_scores
                )
                spin_write_instance.save_current_prompt_scores()

            final_content = current_editable_content
            current_version_num += 1
            chroma_collection.add(
                documents=[final_content],
                metadatas=[{
                    "book_title": book_title,
                    "book_num": book_num,
                    "chapter_num": chapter_num,
                    "version": current_version_num,
                    "type": "final_version",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "editor": name,
                    "reward": reward_value,
                    "levenshtein_ratio_on_finalize": lev_ratio_on_finalize, 
                    "human_rating": human_rating_input if human_rating_input is not None else "Not Rated",
                    "prompt_used_for_spin_before_finalize": prompt_used_for_current_spin    
                }],
                ids=[f"{chapter_base_id}_v{current_version_num}_final"]
            )
            print(f"Chapter finalized and saved to ChromaDB as {chapter_base_id}_v{current_version_num}_final.")
            
            # RL reward for scraping

            original_doc_id = f"{chapter_base_id}_v0_original"
            try:
                # Using ChromaDB's update method directly for efficiency
                chroma_collection.update(
                    ids=[original_doc_id],
                    metadatas=[{"final_chapter_reward": reward_value,
                                "finalized_version_id": "f{chapter_base_id}_v{current_version_num}_final",
                                "finalized_timestamp": datetime.datetime.now().isoformat()}]
                )
                print(f"[RL for Scraping] Updated original document '{original_doc_id}' with final_chapter_reward: {reward_value:.2f}")
            except Exception as e:
                print(f"[RL for Scraping] Error updating original document with reward: {e}")
            break 

        elif choice == '3':
            reward_value = calculate_reward(
                action_choice=choice,
                original_len=len(previous_content_for_edit_check), # Length before this re-spin request
                edited_len=len(previous_content_for_edit_check), # No direct edit, so lengths are the same
                iteration_count=iteration_count,
                human_rating=human_rating_input,
                lev_distance_ratio=1.0 # Treat a re-spin as maximum dissatisfaction with previous content
            )
            print(f"Calculated Reward for 'Re-spin': {reward_value:.2f}")

            if prompt_used_for_current_spin not in ["custom_instruction_override", "fallback_default", "unknown_initial_prompt"]:
                prompt_manager.update_prompt_score(
                    prompt_name=prompt_used_for_current_spin,
                    reward=reward_value,
                    current_scores=spin_write_instance.prompt_scores
                )
                spin_write_instance.save_current_prompt_scores()

            print("\n Re-spin Options\n")
            print("a. Use system's adaptive prompt (based on learning).")
            print("b. Provide a custom instruction.")
            print("c. Generate a completely new prompt using an AI prompt generator.") 
            respin_choice = input("Enter your re-spin choice (a, b, c): ").lower()    

            new_instruction_for_spin_writer = None
            generated_prompt_template_name = None 

            if respin_choice == 'a':
                
                spun_content_current, prompt_used_for_current_spin =await spin_write_instance.ai_spin_content(original_chapter_content, None)

            elif respin_choice == 'b':
                new_instruction_for_spin_writer = input("Enter new custom instruction for AI re-spin: ")
                if not new_instruction_for_spin_writer.strip():
                    print("Custom instruction cannot be empty. Reverting to adaptive prompt.")
                    spun_content_current, prompt_used_for_current_spin = await spin_write_instance.ai_spin_content(original_chapter_content, None)
                else:
                    # If custom instruction, its name for tracking is simply 'custom_instruction_override'
                    spun_content_current, prompt_used_for_current_spin = await spin_write_instance.ai_spin_content(original_chapter_content, new_instruction_for_spin_writer + "\n\n")

            elif respin_choice == 'c':
                print("\nRequesting AI to Generate a New Prompt")
                
                feedback_context_for_generator = (
                    f"The previous AI spin (using prompt '{prompt_used_for_current_spin}') was unsatisfactory, "
                    f"leading to a re-spin request with a reward of {reward_value:.2f} and human rating {human_rating_input}. "
                    "The generated content needs improvement."
                )
                # Get the template of the prompt that just performed poorly for the generator to learn from
                previous_bad_prompt_template = spin_write_instance.prompt_scores.get(prompt_used_for_current_spin, {}).get("template")

                new_generated_template = await prompt_gen_instance.generate_new_prompt_instruction(
                    original_content_snippet=original_chapter_content[:1000], 
                    feedback_context=feedback_context_for_generator,
                    previous_bad_prompt_example=previous_bad_prompt_template,
                    chapter_summary=chapter_summary_for_prompt_gen 
                )

                if new_generated_template:
                    generated_prompt_template_name = f"generated_prompt_{str(uuid.uuid4())[:8]}" # Unique name for new prompt
                    prompt_manager.add_new_prompt_template(
                        name=generated_prompt_template_name,
                        template=new_generated_template,
                        current_scores=spin_write_instance.prompt_scores,
                        initial_score=0.0 
                    )
                    spin_write_instance.save_current_prompt_scores()

                    new_instruction_for_spin_writer = new_generated_template
                    print(f"  [Prompt Generator] New prompt generated and added: '{generated_prompt_template_name}'")
                    print(f"  Generated Template: \"{new_generated_template.strip()}\"")
                    
                    spun_content_current, prompt_used_for_current_spin = await spin_write_instance.ai_spin_content(original_chapter_content, new_instruction_for_spin_writer)
                else:
                    print("Failed to generate a new prompt. Reverting to system's adaptive prompt.")
                    spun_content_current, prompt_used_for_current_spin =await spin_write_instance.ai_spin_content(original_chapter_content, None)
            else:
                print("Invalid re-spin choice. Reverting to system's adaptive prompt.")
                spun_content_current, prompt_used_for_current_spin = await spin_write_instance.ai_spin_content(original_chapter_content, None)

        
            print("\nAI has re-spun the content. Please review again.")
            current_version_num += 1
            previous_content_for_edit_check = current_editable_content

            chroma_collection.add(
                documents=[current_editable_content],
                metadatas=[{
                    "book_title": book_title,
                    "book_num": book_num,
                    "chapter_num": chapter_num,
                    "version": current_version_num, 
                    "type": "ai_spin",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "model_used": sw_model,
                    "instruction": new_instruction_for_spin_writer if new_instruction_for_spin_writer else "adaptive_system_choice",
                    "prompt_template_name": prompt_used_for_current_spin, # Store the actual prompt name used
                    "reward_leading_to_spin": reward_value, # Reward for the action *leading to* this spin
                    "human_rating_leading_to_spin": human_rating_input if human_rating_input is not None else "Not Rated",
                    "generated_by_ai": (respin_choice == 'c'), # Flag if this prompt was AI-generated
                    "prompt_generator_model": pg_model if (respin_choice == 'c') else ""
                
                }],
                ids=[f"{chapter_base_id}_v{current_version_num}_ai_spin"]
            )
            print(f"New AI-spun content v{current_version_num} added to ChromaDB.")
            
            print("\n Re-running AI Reviewer on New Spun Content")
            review_comments_current = await review_instance.ai_review_content(current_editable_content)
            print("\nNew AI Reviewer Comments")
            print(review_comments_current)
            
            chroma_collection.add(
                documents=[review_comments_current],
                metadatas=[{
                    "book_title": book_title,
                    "book_num": book_num,
                    "chapter_num": chapter_num,
                    "version": current_version_num,
                    "type": "ai_review",
                    "timestamp": datetime.datetime.now().isoformat(),
                    "model_used": r_model,
                    "reviewed_version_id": f"{chapter_base_id}_v{current_version_num}_ai_spin"
                }],
                ids=[f"{chapter_base_id}_v{current_version_num}_ai_review"]
            )
            print(f"New AI-review comments v{current_version_num} added to ChromaDB.")

   
        elif choice == '4':
            search_query = input("Enter your search query: ")
            if not search_query.strip():
                print("Search query cannot be empty.")
                continue

            print("\nSemantic Search Options")
            print("You can narrow your search by:")
            print("a. Content Type ('final_version', 'human_edit', 'ai_spin', 'ai_review', 'original')")
            print("b. Specific Book Number")
            print("c. Specific Chapter Number")
            print("d. Specific Version Number (like '3' for version 3)")
            print("e. Specific Editor")
            print("f. Combinations of the above")

            where_clause = []
            content_type_filter = input("Filter by content type (like final_version, human_edit, ai_spin) or leave blank for all: ").strip().lower()
            if content_type_filter:
                valid_types = ["original", "ai_spin", "human_edit", "ai_review", "final_version", "ai_review_after_human"]
                if content_type_filter in valid_types:
                    where_clause.append({"type": content_type_filter}) 
                    print(f"Filtering by content type: '{content_type_filter}'")
                else:
                    print(f"Warning: Invalid content type '{content_type_filter}'. Searching all types.")

            book_num_filter_str = input("Filter by specific Book Number or leave blank for all: ").strip()
            if book_num_filter_str:
                try:
                    book_num_filter = int(book_num_filter_str)
                    where_clause.append({"book_num": book_num_filter}) 
                    print(f"Filtering by Book Number: {book_num_filter}")
                except ValueError:
                    print("Invalid Book Number. Ignoring filter.")

            chapter_num_filter_str = input("Filter by specific Chapter Number or leave blank for all: ").strip()
            if chapter_num_filter_str:
                try:
                    chapter_num_filter = int(chapter_num_filter_str)
                    where_clause.append({"chapter_num": chapter_num_filter}) 
                    print(f"Filtering by Chapter Number: {chapter_num_filter}")
                except ValueError:
                    print("Invalid Chapter Number. Ignoring filter.")

            version_filter_str = input("Filter by specific Version Number or leave blank for all: ").strip()
            if version_filter_str:
                try:
                    version_filter = int(version_filter_str)
                    where_clause.append({"version": version_filter}) 
                    print(f"Filtering by Version: {version_filter}")
                except ValueError:
                    print("Invalid Version Number. Ignoring filter.")

            editor_filter_str = input("Filter by specific editor or leave blank for all: ").strip()
            if editor_filter_str:
                
                where_clause.append({"editor": editor_filter_str}) 
                print(f"Filtering by editor: {editor_filter_str}")


            final_where_clause = None
            if len(where_clause) == 1:
                final_where_clause = where_clause[0] 
            elif len(where_clause) > 1:
                final_where_clause = {"$and": where_clause} 
            

            print("\n Performing Semantic Search ")
            results_n = input("How many results do you want to see (default 5)? ").strip()
            try:
                n_results_int = int(results_n) if results_n else 5
            except ValueError:
                print("Invalid number of results. Defaulting to 5.")
                n_results_int = 5

            try:
                results = chroma_collection.query(
                    query_texts=[search_query],
                    n_results=n_results_int,
                    where=final_where_clause 
                )

                if results['documents'] and results['documents'][0]:
                    print("Found relevant documents:")
                    for i, doc_content in enumerate(results['documents'][0]):
                        metadata = results['metadatas'][0][i]
                        distance = results['distances'][0][i]
                        print(f"\n--- Result {i+1} (Distance: {distance:.4f}) ---")
                        print(f"ID: {results['ids'][0][i]}")
                        print(f"Metadata: {metadata}")
                        print("Content Snippet:")
                        print(doc_content[:500] + "..." if len(doc_content) > 500 else doc_content)
                else:
                    print("No relevant documents found matching your criteria.")
            except Exception as e:
                print(f"An error occurred during semantic search: {e}")
            else:
                print("Search query cannot be empty.")

        elif choice == '5': 
            print("\nPlaying current AI-spun content...")
            speak_text(current_editable_content, "ai_spun_audio.mp3")
            time.sleep(1) 

        elif choice == '6': 
            print("\nPlaying AI Reviewer Comments...")
            speak_text(review_comments_current, "ai_review_audio.mp3")
            time.sleep(1)     

        elif choice == '7': 
            print("Exiting review process.")
            break         
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")



async def main():

    while True:
        print("\n Main Workflow Menu ")
        print("1. Start/Continue Chapter Workflow (for initial chapter)") 
        print("2. Scrape a NEW Chapter and start its Workflow") 
        print("3. Exit") 

        main_choice = input("Enter your choice (1-3): ").strip()

        if main_choice == '1':
            
            # Adjust original_chapter_file to match the unique naming convention
            initial_original_chapter_file = f"scraped_content_{book_name.replace(' ', '_')}_Book{book_num}_Chapter{chap_num}.txt"
            initial_spun_file_path = f"spun_content_{book_name.replace(' ', '_')}_Book{book_num}_Chapter{chap_num}.txt"
            initial_review_file_path = f"reviewer_comments_{book_name.replace(' ', '_')}_Book{book_num}_Chapter{chap_num}.txt"


            if not os.path.exists(initial_original_chapter_file):
                print(f"Performing initial scrape for default chapter ({book_name} Book {book_num} Chapter {chap_num})...")
                scraped_text_default, _, _, is_valid_default =await scrape.scrape_content(
                    book_name.replace(' ', '_'), book_num, chap_num
                )
                if not is_valid_default:
                    print(f"Error: Default chapter {book_name} Book {book_num} Chapter {chap_num} could not be scraped. Returning to main menu.")
                    continue # Return to main menu if default chapter is invalid
                original_chapter_content_for_default = scraped_text_default
            else:
                original_chapter_content_for_default = load_content(initial_original_chapter_file)
                if original_chapter_content_for_default is None:
                    print(f"Failed to load existing original chapter content for default: {initial_original_chapter_file}. Returning to main menu.")
                    continue


            initial_prompt_name_for_workflow = "unknown_initial_prompt"


            if not os.path.exists(initial_spun_file_path) or not os.path.exists(initial_review_file_path):
                print("Initial AI spin/review files not found for default chapter. Generating them now using adaptive prompt...")
                spun_content_for_init, initial_prompt_name_for_workflow = await spin_write_instance.ai_spin_content(original_chapter_content_for_default, None)
                with open(initial_spun_file_path, 'w', encoding='utf-8') as f: f.write(spun_content_for_init)
                review_comments_for_init = await review_instance.ai_review_content(spun_content_for_init)
                with open(initial_review_file_path, 'w', encoding='utf-8') as f: f.write(review_comments_for_init)
                print(f"Initial spin for default chapter used prompt: '{initial_prompt_name_for_workflow}'")
            else:
                print("Initial AI spin/review files for default chapter already exist. Loading them.")
                
                pass
                

            
            await human_in_the_loop_workflow(
                original_content_path=initial_original_chapter_file,
                initial_spun_content_path=initial_spun_file_path,
                initial_review_comments_path=initial_review_file_path,
                book_title=book_name, # Use global book_name
                book_num=book_num,   # Use global book_num
                chapter_num=chap_num, # Use global chap_num
                chroma_collection=collection,
                current_version_num=1,
                prompt_used_for_current_spin_on_start=initial_prompt_name_for_workflow,
                original_chapter_content=original_chapter_content_for_default # Pass the content that was just loaded/scraped
            )
            print("\n Returned to Main Menu after Default Chapter Workflow ")
        
        elif main_choice == '2': 
            await scrape_new(collection)
            print("\n Returned to Main Menu after New Chapter Workflow ")


        elif main_choice == '3': # Exit option
            print("Exiting application. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    asyncio.run(main())

    
    
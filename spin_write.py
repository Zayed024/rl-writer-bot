import google.generativeai as genai
import os
import prompt_manager
import asyncio

spin_write_model='gemini-1.5-flash' #can use gemini-1.5-pro 
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please set it before running the script.")
        exit()



class SpinWrite:
    def __init__(self, model_name=spin_write_model): 
        self.model_name = model_name
        self.model = genai.GenerativeModel(self.model_name)
        self.summodel_name="gemini-2.5-flash"
        self.summodel = genai.GenerativeModel(self.summodel_name)
        
        self.prompt_scores = prompt_manager.load_prompt_scores()
        print("[SpinWrite] Initialized with prompt scores.")

    async def ai_summarize(self,original_content: str) -> str:
        prompt=("Summarize the following text concisely, focusing on the main plot points,characters, and setting.\n\n" 
            )
        full_prompt=prompt + original_content

        try:
            response = await self.summodel.generate_content_async(full_prompt)
            # Checking if the response has text content
            if response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text
            else:
                print("Warning: Gemini response had no text content for summarizing.")
                return "Failed to summarize content."
        except Exception as e:
            print(f"Error during AI content summarization: {e}")
            return "Failed to summarize content due to an error."


    async def ai_spin_content(self,original_content: str, prompt_instruction: str = None) -> (str, str):

        chosen_prompt_name = None
        prompt_template_text = None

        if prompt_instruction is None:
            # If no specific instruction provided, use adaptive prompting
            chosen_prompt_name, prompt_template_text = prompt_manager.get_adaptive_prompt(self.prompt_scores)
        else:
            # If a specific instruction is provided 
            # treating this as a "custom" instruction for the purpose of the adaptive system.
            
            prompt_template_text = prompt_instruction
            # For logging purposes, if this came from generator, its name will be passed back.
            

            chosen_prompt_name = "custom_instruction_override"


        if prompt_template_text is None:
            print("Error: Could not determine prompt template. Using a very basic default.")
            prompt_template_text = "Rewrite the following text:\n\n"
            chosen_prompt_name = "fallback_default"


        full_prompt = prompt_template_text  + "Text to rewrite:\n\n" + original_content

        try:
            response = await self.model.generate_content_async(full_prompt)
           
            if response.candidates and response.candidates[0].content.parts:
                spun_text = response.candidates[0].content.parts[0].text
                return spun_text,chosen_prompt_name
            else:
                print("Warning: Gemini response had no text content for spinning.")
                return "Failed to spin content."
        except Exception as e:
            print(f"Error during AI content spinning: {e}")
            return "Failed to spin content due to an error."
        
    def save_current_prompt_scores(self):
        """Saves the current state of prompt scores via prompt_manager."""
        prompt_manager.save_prompt_scores(self.prompt_scores)

async def main():
    
    input_file = "scraped_content.txt" 
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            chapter_content = f.read()
        print("Successfully loaded content")
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        
        exit()

    
    print("\n AI Writer: Spinning Content")
    spin_writer = SpinWrite()
    spun_chapter, chosen_prompt = await spin_writer.ai_spin_content(chapter_content)
    print("\nSpun Chapter Content")
    

    output_spun_file = "spun_content.txt"
    with open(output_spun_file, 'w', encoding='utf-8') as f:
        f.write(spun_chapter)
    print(f"\nAI-spun content saved to {output_spun_file}")

if __name__ == "__main__":
    asyncio.run(main()) # Run the async main function
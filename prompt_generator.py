# prompt_generator.py
import google.generativeai as genai
import os
import asyncio



try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Error: GEMINI_API_KEY environment variable not set in prompt_generator.py.")
    print("Please set it before running the script.")
    exit()

class PromptGenerator:
    def __init__(self, model_name='gemini-1.5-pro-latest'): 
        self.model_name = model_name
        self.model = genai.GenerativeModel(self.model_name)
        print(f"[Prompt Generator] Initialized with model: {self.model_name}")

    async def generate_new_prompt_instruction(self,
                                        original_content_snippet: str,
                                        feedback_context: str = None,
                                        previous_bad_prompt_example: str = None,
                                        chapter_summary: str = None
                                        ) -> str:
        """
        Generates a new prompt instruction for the AI writer based on provided context and feedback.

        Args:
            original_content_snippet (str): A short snippet (like first 500 chars) of the original text
                                            to provide thematic and stylistic context for the new prompt.
            feedback_context (str, optional): A description of what went wrong with previous attempts.
                                            
            previous_bad_prompt_example (str, optional): The exact prompt text that led to poor results.
                                                        Used as a negative example to learn from.
            chapter_summary (str, optional): A brief summary of the overall chapter/book context for thematic consistency.

        Returns:
            str: A newly generated prompt instruction 
                 
        """
        # System instruction guides the behavior of the prompt generator LLM itself
        system_instruction = (
            "You are an expert prompt engineer specializing in crafting precise and effective "
            "instructions for AI text generation models. Your goal is to generate a concise, "
            "clear, and unique prompt instruction that guides an AI writer to rewrite text. "
            "The instruction should focus on style, tone, descriptive detail, conciseness, or overall impact. "
            "Provide ONLY the prompt instruction text, without any conversational filler, explanations, "
            "or examples. The instruction should implicitly ask the AI to rewrite the following text. "
            "Ensure the instruction is distinct from common, generic prompts."
        )

        
        user_prompt_parts = []
        user_prompt_parts.append(f"Here's a snippet of the original content for context:\n\n{original_content_snippet[:500]}...\n\n\n")

        if chapter_summary:
            user_prompt_parts.append(f"Overall chapter summary/theme: \"{chapter_summary}\"\n\n")

        if feedback_context:
            user_prompt_parts.append(f"Previous attempts received the following feedback: {feedback_context}\n")
        if previous_bad_prompt_example:
            user_prompt_parts.append(f"The prompt that performed poorly was:\n\n\"{previous_bad_prompt_example.strip()}\"\n\n")
            user_prompt_parts.append("Generate a NEW and DIFFERENT prompt instruction for rewriting this text, aiming to improve based on the feedback and avoiding the previous style.\n")
        else:
            user_prompt_parts.append("Generate a new and creative prompt instruction for rewriting text, focusing on a unique stylistic or tonal transformation.\n")

        user_prompt_parts.append("New Prompt Instruction (start directly with the instruction):")
        
        full_user_prompt = "".join(user_prompt_parts)

        try:
            print(f"  [Prompt Generator] Requesting new prompt from model: {self.model_name}...")
            response = await self.model.generate_content_async(
                contents=[
                    {"role": "user", "parts": [{"text": system_instruction}]},
                    {"role": "user", "parts": [{"text": full_user_prompt}]}
                ],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7, # Higher temperature for more creative prompts
                    max_output_tokens=250
                )
            )
            
            if response.candidates and response.candidates[0].content.parts:
                generated_prompt = response.candidates[0].content.parts[0].text.strip()
                
                if not generated_prompt.endswith("\n\n"):
                    generated_prompt += "\n\n"
                return generated_prompt
            else:
                print("  [Prompt Generator] Warning: Gemini response had no text content for new prompt generation.")
                return None
        except Exception as e:
            print(f"  [Prompt Generator] Error during new prompt generation: {e}")
            return None
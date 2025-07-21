import google.generativeai as genai
import os
import asyncio

review_model='gemini-1.5-pro'  #specify model here

try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Error: GEMINI_API_KEY environment variable not set.")
    print("Please set it before running the script.")
    exit()



class Review:
    def __init__(self, model_name=review_model):
        self.model_name = model_name
        self.model = genai.GenerativeModel(self.model_name)


    async def ai_review_content(self,content_to_review: str) -> str:
        
        prompt = (
            "You are an experienced book editor. Review the following chapter for clarity, coherence, grammar, spelling, "
            "punctuation, consistency in tone, and overall readability. "
            "Provide actionable feedback and specific suggestions for improvement. "
            "give output in normal text format, not markdown. "
            "dont use any extra text highlighting like using asterisks before and after words. "
            "Structure your feedback clearly, perhaps using bullet points or numbered lists, and reference specific paragraphs or sentences where possible.\n\n"
            "Here is the content to review:\n\n" + content_to_review
        )

        try:
            response = await self.model.generate_content_async(prompt)
            if response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text
            else:
                print("Warning: Gemini response had no text content for reviewing.")
                return "Failed to review content."
        except Exception as e:
            print(f"Error during AI content reviewing: {e}")
            return "Failed to review content due to an error."



    
    
        
        

    

    
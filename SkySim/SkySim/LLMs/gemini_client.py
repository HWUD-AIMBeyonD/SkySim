import os
import sys
import ast
from google import genai
from google.genai import types
from dotenv import load_dotenv

class GeminiClient:

    @staticmethod
    def list_available_models(api_key=None):
        """
        List available Gemini models that support content generation.
        """
        try:
            if not api_key:
                env_path = '/home/aditya/SkySim/.env'
                load_dotenv(dotenv_path=env_path)
                api_key = os.getenv('GEMINI_API_KEY') or os.getenv('API_KEY')

            if not api_key:
                return []

            client = genai.Client(api_key=api_key)
            # The new SDK listing method might differ, assuming standard list logic or skipping for now as it's a helper. 
            # For simplicity in this migration, returning a hardcoded list of known good models 
            # or wrapping a try-catch if using the old style. 
            # The new SDK documentation suggests client.models.list()
            
            models = client.models.list()
            model_names = []
            for m in models:
                # Basic check, structure might vary
                if hasattr(m, 'name'):
                    name = m.name.replace('models/', '')
                    model_names.append(name)
            return model_names
        except Exception as e:
            print(f"Error listing models: {e}")
            return []

    def __init__(self, model_name='gemini-3-pro-preview', logger=None):
        self.logger = logger
        self.model_name = model_name
        
        env_path = '/home/aditya/SkySim/.env'
        loaded = load_dotenv(dotenv_path=env_path)
        
        self._log(f"DEBUG: Loading .env from {env_path}, Success: {loaded}")
        
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            self.api_key = os.getenv('API_KEY')
            
        self._log(f"DEBUG: GEMINI_API_KEY (or API_KEY) found: {bool(self.api_key)}")
        
        if not self.api_key:
            self._log("Warning: GEMINI_API_KEY environment variable not set or .env not loaded.", level='warn')
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                self._log(f"Gemini Client initialized with model: {self.model_name}")
            except Exception as e:
                self._log(f"Failed to initialize Gemini Client: {e}", level='error')
                self.client = None
    
    def _log(self, msg, level='info'):
        if self.logger:
            if level == 'warn':
                self.logger.warn(msg)
            elif level == 'error':
                self.logger.error(msg)
            else:
                self.logger.info(msg)
        else:
            print(msg)
            sys.stdout.flush()

    def generate_waypoints(self, user_prompt, num_drones, current_positions=None):
        """
        Generates a list of [x, y, z] coordinates for the swarm based on the user prompt.
        """
        if not self.client:
             self._log("Error: Gemini Client not initialized.", level='error')
             return None

        system_instruction = (
            f"You are a drone swarm controller for {num_drones} drones. "
            "You will receive a user command and potentially current positions. "
            "Your task is to generate target [x, y, z] coordinates for each drone to fulfill the command. "
            f"IMPORTANT: Output ONLY a valid Python list of {num_drones} lists, representing the target [x, y, z] for each drone respectively. "
            f"Example Output: [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0], ... (total {num_drones} items)] "
            "Do not include any markdown formatting, explanations, or code blocks. Just the raw list string. "
            "Keep z >= 0.5 to avoid crashing into the ground. "
            "Coordinate system: X is forward, Y is left, Z is up."
        )
        
        context_str = ""
        if current_positions:
            context_str = f"Current Drone Positions: {current_positions}\n"

        final_prompt = f"{system_instruction}\n\n{context_str}User Command: {user_prompt}"
        
        try:
            # New SDK call
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=final_prompt
            )
            
            response_text = response.text.strip()
            self._log(f"DEBUG: Raw LLM Response: {response_text}")
            
            if response_text.startswith("```"):
                response_text = response_text.strip("`").replace("python", "").replace("json", "").strip()
            
            waypoints = ast.literal_eval(response_text)
            
            if not isinstance(waypoints, list) or len(waypoints) != num_drones:
                self._log(f"Error: Output must be a list of {num_drones} coordinates. Got: {waypoints}", level='error')
                return None
            
            for pt in waypoints:
                if not isinstance(pt, (list, tuple)) or len(pt) != 3:
                     self._log(f"Error: Invalid coordinate format: {pt}", level='error')
                     return None
                     
            return waypoints

        except Exception as e:
            self._log(f"Error generating waypoints: {e}", level='error')
            return None
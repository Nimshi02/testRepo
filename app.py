import numpy as np
from keras.models import Sequential
from keras.layers import Dense
from keras.utils import to_categorical
import pandas as pd
import json
import datetime
import re
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import firestore
from IPython.core.display import set_matplotlib_formats
from flask import Flask, jsonify
# #Load the database
df=pd.read_json("ingredient_and_instructions.json")
# #Initialize recipes variable
recipes = {}
# #Initialize the new recipe to be added to the recipe
new_recipe = {}
# #Define the quantity 
quantity=0
# #clean the recipe array
for items in df:
  new_recipe = {}
  itemName=items
  ingredient_sections = df[items]["ingredient_sections"]
  for section in ingredient_sections:
    ingredients = section["ingredients"]
    for ingredient in ingredients:
      name = ingredient["name"]
      primary_unit = ingredient["primary_unit"]
      metric_unit = ingredient["metric_unit"]
      if metric_unit is not None:
        quantity=float(metric_unit["quantity"])
      else:
        if primary_unit is not None:
          if primary_unit["display"] is None:
            quantity=2
          else:
            if primary_unit["display"] == "teaspoons" or primary_unit["display"] == "teaspoon":
                string_value = str(primary_unit["quantity"])
                cleaned_string = re.sub(r'[^\d.]', '', string_value)
                if cleaned_string:
                  int_value = float(cleaned_string)
                  quantity=int_value*5
            else:
              if primary_unit["display"] == "tablespoon" or primary_unit["display"] == "tablespoons":
                if primary_unit["quantity"] is not None:
                  string_value = str(primary_unit["quantity"])
                  cleaned_string = re.sub(r'[^\d.]', '', string_value)
                  if cleaned_string:
                    int_value = float(cleaned_string)
                    quantity=int_value*15
        else:
         quantity=2
      new_ingredient = name
      new_amount = quantity
      new_recipe[new_ingredient] = new_amount
  recipes[itemName] = new_recipe

print(recipes)
all_ingredients = set()
for recipe in recipes.values():
    all_ingredients.update(recipe.keys())

#Create the numpy array of recipes
recipe_names = list(recipes.keys())
num_recipes = len(recipe_names)
print(num_recipes)
num_ingredients = len(all_ingredients)
recipe_matrix = np.zeros((num_recipes, num_ingredients))

ingredient_to_index = {ingredient: i for i, ingredient in enumerate(all_ingredients)}
for i, recipe_name in enumerate(recipe_names):
    recipe = recipes[recipe_name]
    for ingredient, quantity in recipe.items():
        j = ingredient_to_index[ingredient]
        recipe_matrix[i, j] = quantity

# # Define the neural network
model = Sequential()
model.add(Dense(8, input_dim=len(all_ingredients), activation='relu'))
model.add(Dense(4, activation='relu'))
model.add(Dense(len(recipe_names), activation='softmax'))

# # # Compile the model
model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

# # # Fit the model to the data
labels = to_categorical(np.arange(len(recipe_names)), len(recipe_names))
model.fit(recipe_matrix, labels, epochs=10, batch_size=10)

app = Flask(__name__)
@app.route('/recipes', methods=['GET'])
def get_recipes():
# # # get the user ingredients and create a dictionary
# # ########################
#Get the user creadentials
  cred = credentials.Certificate('newProject-service.json')
  if len(firebase_admin._apps) == 0:
      firebase_admin.initialize_app(cred)
      print("Firebase connection not established.")
  else:
      print("Firebase connection established.")

  db = firestore.client()
  collection_ref = db.collection("Ingredients")

  docs = collection_ref.get()

  #creating a dictionary to store the firebase derived values 
  posess_ingredients={}

  # Iterate over the documents and print their data
  for doc in docs:
      qty = doc.get("Qty")
      name = doc.get("ItemName")
      expire_date_str = doc.get("Expiredate")
      expire_date = datetime.datetime.strptime(expire_date_str, '%d/%m/%Y')
      days_to_expire = (expire_date - datetime.datetime.today()).days
      newIngredient = {"expiration_date": days_to_expire, "quantity": qty}
      posess_ingredients.update({name: newIngredient})
  user_ingredients=posess_ingredients
  print(user_ingredients)
  #create numpy array of user_ingredients
  user_vector = np.zeros((1, len(all_ingredients)))
  for i, ingredient in enumerate(all_ingredients):
      if ingredient in user_ingredients:
          user_vector[0, i] = user_ingredients[ingredient]['quantity']
  recipes_array = np.array(user_vector)
  print(recipes_array)

  # Multiply user vector by trained recipe matrix 
  scores = np.dot(recipes_array, recipe_matrix.T)[0]
  print(scores)

  # Get top scoring recipes
  top_indices = np.argsort(scores)[::-1][:10]

  # Get names of top-scoring recipes
  top_recipes = []
  for index in top_indices:
      top_recipes.append(recipe_names[index])
  print(top_recipes)


  # For each top-scoring recipe, calculate the expiration date of its ingredients
  # Get names of top-scoring recipes
  recipe_expiration_dates = {}
  for recipe_name in recipe_names:
      recipe = recipes[recipe_name]
      recipe_expiration_dates[recipe_name] = min([user_ingredients.get(ingredient, {'expiration_date': float('inf')})['expiration_date'] for ingredient in recipe.keys()])
  print(recipe_expiration_dates)
  # Sort the top recipes by their expiration date
  sorted_top_recipes = sorted(top_recipes, key=lambda x: recipe_expiration_dates[x])

  # Print the top recipes in order of expiration date
  payload=[]
  for recipe_name in sorted_top_recipes:
      
      ingredients=recipes[recipe_name]
      # print(recipe_name, recipe_expiration_dates[recipe_name])
      for items in df:
          itemName=items
          if itemName == recipe_name :
            instructions=df[items]["instructions"]
            break
      recipe_item = {
        "name": recipe_name,
        "ingredients": [
          ingredients
        ],
        "instructions": instructions
	"user_ingredients": recipes_array
        }
      payload.append(recipe_item)
  json_payload = json.dumps(payload)
  return jsonify(payload)
if __name__ == '__main__':
    app.run(host='localhost', port=5000,debug=False)

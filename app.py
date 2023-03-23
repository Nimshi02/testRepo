

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

app = Flask(__name__)


#Load the database
df=pd.read_json("ingredient_and_instructions.json")

#Initialize recipes variable
recipes = {}

#Initialize the new recipe to be added to the recipe
new_recipe = {}

#Define the quantity 
quantity=0

#Create the recipes array
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
        quantity=int(metric_unit["quantity"])
      else:
        if primary_unit is not None:
          if primary_unit["display"] is None:
            quantity=2
          else:
            if primary_unit["display"] == "teaspoons" or primary_unit["display"] == "teaspoon":
                string_value = str(primary_unit["quantity"])
                cleaned_string = re.sub(r'[^\d.]', '', string_value)
                if cleaned_string:
                  int_value = int(cleaned_string)
                  quantity=int_value*5
            else:
              if primary_unit["display"] == "tablespoon" or primary_unit["display"] == "tablespoons":
                if primary_unit["quantity"] is not None:
                  string_value = str(primary_unit["quantity"])
                  cleaned_string = re.sub(r'[^\d.]', '', string_value)
                  if cleaned_string:
                    int_value = int(cleaned_string)
                    quantity=int_value*15
        else:
         quantity=2
      new_ingredient = name
      new_amount = quantity
      new_recipe[new_ingredient] = new_amount
  recipes[itemName] = new_recipe
print(recipes)


recipe_names = list(recipes.keys())

# Find the unique ingredients in all the recipes
all_ingredients = set()
for recipe in recipes.values():
    for ingredient in recipe.keys():
        all_ingredients.add(ingredient)

all_ingredients = list(all_ingredients)

# Convert the table of recipes to a numpy array
recipes_array = []
for recipe in recipes.values():
    recipe_ingredients = []
    for ingredient in all_ingredients:
        if ingredient in recipe:
            recipe_ingredients.append(recipe[ingredient])
        else:
            recipe_ingredients.append(0)
    recipes_array.append(recipe_ingredients)

recipes_array = np.array(recipes_array)

# Define the neural network
model = Sequential()
model.add(Dense(8, input_dim=len(all_ingredients), activation='relu'))
model.add(Dense(4, activation='relu'))
model.add(Dense(len(recipe_names), activation='softmax'))

# Compile the model
model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

# Fit the model to the data
labels = to_categorical(np.arange(len(recipe_names)), len(recipe_names))
model.fit(recipes_array, labels, epochs=10, batch_size=1)


########################
cred = credentials.Certificate('newProject-service.json')
if len(firebase_admin._apps) == 0:
    firebase_admin.initialize_app(cred)
    print("Firebase connection established.")
else:
    print("Firebase connection not established.")

db = firestore.client()
collection_ref = db.collection("Ingredients")

docs = collection_ref.get()

#creating a dictionary to store the firebase derived values 
posess_ingredients={}

# Iterate over the documents and print their data
for doc in docs:
 qty = doc.get("Qty")
 name=doc.get("ItemName")
 expireDate=doc.get("Expiredate")
 days_to_expire = (datetime.datetime.strptime(expireDate, "%d/%m/%Y") - datetime.datetime.today()).days
 newIngredient={"expire_date":days_to_expire,"qty":qty}
 posess_ingredients.update({name:newIngredient})
print(posess_ingredients)



# Check if the ingredients entered by the user are sufficient to create one of the recipes
ingredient_array = []
for ingredient in all_ingredients:
    if ingredient in posess_ingredients:
        ingredient_array.append(posess_ingredients[ingredient]["qty"])
    else:
        ingredient_array.append(0)
        
ingredient_array = np.array([ingredient_array])

results = model.predict(ingredient_array)

# @app.route('/predict-recipes', methods=['GET'])
# def predict_recipes():
  
# satisfied_recipes = []
# for index, result in enumerate(results[0]):
#     satisfied_recipes.append((recipe_names[index], result))

# if len(satisfied_recipes) > 0.5:
#     print("The following recipes are likely to be satisfied by the remaining ingredients:")
#     # Sort the satisfied_recipes based on the ascending order of the possessed ingredient's expire date
#     very_distant_date = datetime.datetime.max.replace(year=9999)

#     sorted_recipes = sorted(satisfied_recipes, key=lambda x: posess_ingredients.get(x[0], {}).get("expire_date", very_distant_date))
#     for recipe in sorted_recipes:
#         if recipe[1] > 0:
#             print(recipe[0])
#             for ingredient, quantity in recipes[recipe[0]].items():
#                 print(ingredient, quantity)
#     print()
# else:
#     print("No recipes are likely to be satisfied")

@app.route('/recipes', methods=['GET'])
def get_recipes():
    

    satisfied_recipes = []
    for index, result in enumerate(results[0]):
        satisfied_recipes.append((recipe_names[index], result))

    if len(satisfied_recipes) > 0.5:
        # Sort the satisfied_recipes based on the ascending order of the possessed ingredient's expire date
        very_distant_date = datetime.datetime.max.replace(year=9999)
        sorted_recipes = sorted(satisfied_recipes, key=lambda x: posess_ingredients.get(x[0], {}).get("expire_date", very_distant_date))
        
        # Create a dictionary to store the recipe names and ingredients
        response = {}
        for recipe in sorted_recipes:
            if recipe[1] > 0:
                recipe_name = recipe[0]
                recipe_ingredients = []
                for ingredient, quantity in recipes[recipe_name].items():
                    recipe_ingredients.append({'name': ingredient, 'quantity': quantity})
                response[recipe_name] = recipe_ingredients
        
        # Return the response as JSON
        return jsonify(response)
    else:
        # Return a message indicating that no recipes are likely to be satisfied
        return jsonify({'message': 'No recipes are likely to be satisfied'})

if __name__ == '__main__':
    app.run(host='localhost', port=5000,debug=False)
import urllib2, json, string, base64, re, sys
from bs4 import BeautifulSoup
from textstat.textstat import textstat
from flask import Flask, render_template, request, json

scored_recipes = []
mainIngredientRecipes = []
commonCupboard = ['salt','egg','eggs','butter','oil','sugar','granulated sugar','pepper','garlic','milk','all-purpose flour','flour','water']

app = Flask(__name__)

@app.route("/")
def main():
	return render_template('index.html')

@app.route("/recipe-list", methods=['POST'])
def recipeList():
	ingredient1 = request.form['ingredient1'].encode('ascii','ignore')
	ingredient2 = request.form['ingredient2'].encode('ascii','ignore')
	ingredient3 = request.form['ingredient3'].encode('ascii','ignore')
	ingredient4 = request.form['ingredient4'].encode('ascii','ignore')

	allowedIngredients = []
	allowedIngredients.append(ingredient1)
	allowedIngredients.append(ingredient2)
	allowedIngredients.append(ingredient3)
	allowedIngredients.append(ingredient4)

	begin_recipe_searching(allowedIngredients, [], [])

	return render_template('recipe-list.html')

@app.route("/recipe-list/view")
def viewRecipeList():
	return render_template('recipe-list.html')

# replaces common characters in URL queries with appropriately formatted characters
def replace_chars(query):
	query = string.replace(query, "'", '%27')
	query = string.replace(query, '"', '%27')
	query = string.replace(query, '+', '%2b')
	query = string.replace(query, ' ', '%20')
	query = string.replace(query, ':', '%3a')
	query = string.replace(query, '(', '%28')
	query = string.replace(query, ')', '%29')
	query = string.replace(query, '[', '%5b')
	query = string.replace(query, ']', '%5d')
	return query

# uses the urllib function to grab the response to a HTTP GET request
def process_request(url):
	request = urllib2.Request(url)
	requestOpener = urllib2.build_opener()
	response = requestOpener.open(request)
	results = json.load(response)
	return results

# returns the approximate grade-level needed to read the text
# used the formula obtained from wikipedia
def flesch_kincaid_score(text):
	sylCount = textstat.syllable_count(text)
	wordCount = len(text.split())
	sentenceCount = textstat.sentence_count(text)

	print "Syl count - %s, word count - %s, sentenceCount - %s " % (sylCount,wordCount,sentenceCount)

	return (0.39*(wordCount/sentenceCount)+11.8*(sylCount/wordCount) - 15.59)

def ing_on_hand(onHand,inRecipe):
	onHandList = []
	onHandList.extend(onHand)
	onHandList.extend(commonCupboard)
	onHandIngredients = [x for x in onHandList for y in inRecipe if x in y.split() if len(y) > 1]
	return onHandIngredients

# Calls the Yummly API to get details of a specific recipe
def get_recipe(recipeID, yummlyCredentials):
	recipeURL = 'http://api.yummly.com/v1/api/recipe/%s?%s' % (recipeID, yummlyCredentials)
	recipeInfo = process_request(recipeURL)
	return recipeInfo

# Scrapes the source HTML page gathered from the yummly api for recipe directions 
# currently only works with recipes taken from foodnetwork.com
def get_directions(url):
	page = urllib2.urlopen(url)
	soup = BeautifulSoup(page, "html.parser")

	direction_soup = soup.find_all(itemprop='recipeInstructions')[0].p
	directions = direction_soup.get_text() + "\n"
	siblings = direction_soup.find_next_siblings("p")
	siblings = siblings[:-2]

	for sibling in siblings:
		directions += sibling.get_text() + "\n"

	return directions

# main algorithm for project
# Extracts all necessary data from the yummly api, and calls the simplicity algorithm
def evaluate_recipe(allowedIngredients, recipe):
	recipeName = recipe['name'].encode('ascii','ignore')
	print "evaluating %s" % recipeName
	
	sourceDict = recipe['source']
	sourceName = sourceDict['sourceDisplayName'].encode('ascii','ignore')
	directionsText = ""

	# currently, only Food Network sources work. 
	if "Food Network" in sourceName:
		directionsText = get_directions(sourceDict['sourceRecipeUrl'])
		print directionsText
	else:
		return

	prepTime = 0
	if 'prepTimeInSeconds' in recipe:
		prepTime = recipe['prepTimeInSeconds']

	cookTime = 0
	if 'cookTimeInSeconds' in recipe:
		cookTime = recipe['cookTimeInSeconds']
	else:
		if prepTime == 0: # API returned non-specific cooking time
			cookTime = recipe['totalTimeInSeconds'] # will use total time as cook time in algorithm instead

	ingredientList = recipe['ingredientLines']
	numTotalIngredients = len(ingredientList)
	ingOnHand = ing_on_hand(allowedIngredients, mainIngredientRecipes[mainIngredientRecipes.index(recipe['id'])+1])
	numMissingIngr = numTotalIngredients - len(ingOnHand)

	flavors = recipe['flavors']

	if directionsText:
		simplicityScore = evaluate_simplicity(numTotalIngredients,prepTime,cookTime,numMissingIngr,directionsText)
		scored_recipes.append((recipeName,simplicityScore))

# Assigns a score to a recipe based upon a number of factors 
def evaluate_simplicity(numIng, prepTime, cookTime, numMissingIngr, directionsText):
	numIngConst = 0.6
	prepConst = 0.0015
	cookConst = 0.001
	missingIngrConst = 2.0
	fkConst = 0.5
	stepsConst = 0.3

	fkScore = flesch_kincaid_score(directionsText)
	numSteps = len([s.strip() for s in directionsText.splitlines()])


	return numIngConst*numIng + prepConst*prepTime + cookConst*cookTime + missingIngrConst*numMissingIngr + fkConst*fkScore + stepsConst*numSteps

def printResults(ingList):
	print 'The simplest recipes for the ingredients ' + str(ingList) + ' are the following:'
	i = 0
	while i < len(scored_recipes):
		print str(i+1) + '. ' + str(scored_recipes[i])
		i += 1
	
def begin_recipe_searching(allowedIngredients, disallowedIngredients, cuisineType):
	#credentials structure: _app_id=app-id&_app_key=app-key
	yummlyAppID = "1a10b2e0"
	yummlyAppKey = "72595b3dee46471a8a93caa35baf8ef1"
	yummlyCredentials = '%s=%s&%s=%s' % ('_app_id', yummlyAppID, '_app_key', yummlyAppKey)
			
	urlQuery = "q=Food+Network"
	urlIngredients = ''
	print allowedIngredients
	for ing in allowedIngredients:
		if ing:
			print "the ingredient is " + ing
			print ing.strip()
			urlIngredients = urlIngredients + '&allowedIngredient[]=%s' % ing.strip()

	recipeSource = "&allowedSource=Food+Network"

	searchParamenters = urlQuery + urlIngredients + recipeSource + '&maxResult=5'
	#print searchParamenters
	
	url = 'http://api.yummly.com/v1/api/recipes?%s&%s' % (yummlyCredentials, searchParamenters)
	print url
	results = process_request(url)
	
	completeRecipes = []
	for item in results["matches"]:
		#print item['id']
		mainIngredientRecipes.append(item['id'])
		mainIngredientRecipes.append(item['ingredients'])
		completeRecipes.append(get_recipe(item['id'], yummlyCredentials))
		
	# evaluate the simplicity for every recipe gathered
	for item in completeRecipes:
		evaluate_recipe(allowedIngredients, item)
	
	scored_recipes.sort(key=lambda number: number[-1])

	printResults(allowedIngredients)
	
	#print results

if __name__ == "__main__":
	app.run()
import sys
import json
from random import randrange
from traceback import format_exc
from shutil import copyfile

GRID_HEIGHT = 16
GRID_WIDTH = 16

# I'm not putting emoji everywhere in the code
MYSTERY = '❔'
FLAG = '🚩'
WRONGLY_FLAGGED = '❌'
EXPLOSION = '💥'
ADJACENT = ('⬛', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣')

# Bounds check
def isValid(x, y):
    return (0 <= x < GRID_WIDTH) and (0 <= y < GRID_HEIGHT)

# Shorter way to write over files opened in mode r+
def overwriteAndClose(file, text):
    file.seek(0)
    file.truncate()
    file.write(text)
    file.close()

# Includes diagonally adjacent mines (0-8)
def getNumAdjacentMines(x, y, mineList):
    deltas = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    numAdjacent = 0

    for delta in deltas:
        checkPoint = [x + delta[0], y + delta[1]]
        if checkPoint in mineList:
            numAdjacent += 1
    
    return numAdjacent

# Renders 2D list as Markdown table string
def toMarkdown(data):
    tableWidth = len(data[0])

    renderedField = "|" * (tableWidth + 1) + "\n|" + "-|" * tableWidth + "\n"
    renderedField += "\n".join(map(lambda x: "|".join(x), data))

    return renderedField

# Be nice to the user on their first dig: clear out some space
def generateMines(numMines, initialX, initialY):
    generatedMines = []
    while len(generatedMines) < numMines:
        newMine = [randrange(0, GRID_WIDTH), randrange(0, GRID_HEIGHT)]

        if newMine not in generatedMines and \
            newMine != [initialX, initialY] and \
            getNumAdjacentMines(initialX, initialY, [newMine]) == 0:
                generatedMines.append(newMine)
    
    return generatedMines

def main():

    # Only relevant in the context of GitHub Actions
    actionsEnv = "encrypt=false"

    try:

        # Grab selected point from command line args
        if(len(sys.argv) - 1 != 2):
            raise ValueError("Invalid input")

        point = json.loads(sys.argv[2])
        selectedX = round(point[0])
        selectedY = round(point[1])
        if not isValid(selectedX, selectedY):
            raise ValueError("Invalid input")

        file = open("mines.json", "r+", encoding="utf8")
        mines = json.load(file)

        # If needs new game
        if not mines:
            mines = generateMines(40, selectedX, selectedY)
            actionsEnv = "encrypt=true"
        overwriteAndClose(file, json.dumps(mines))

        file = open("field.json", "r+", encoding="utf8")
        fieldArray = json.load(file)

        gameOver = False

        if "game_flag" in sys.argv[1]:
            selectedCell = fieldArray[selectedY][selectedX]

            # Flag
            if MYSTERY in selectedCell:
                fieldArray[selectedY][selectedX] = selectedCell \
                    .replace("=game_dig", "=game_flag") \
                    .replace(MYSTERY, FLAG)

            # Unflag
            elif FLAG in selectedCell:
                templateJSONFile = open("template/field.json", "r", encoding="utf8")
                fieldArray[selectedY][selectedX] = json.load(templateJSONFile)[selectedY][selectedX]
                templateJSONFile.close()

        elif ("game_dig" in sys.argv[1]) and [selectedX, selectedY] in mines:

            # Game over, mark mines and which ones were wrongly flagged
            gameOver = True

            for mine in mines:
                if FLAG in fieldArray[mine[1]][mine[0]]:
                    fieldArray[mine[1]][mine[0]] = WRONGLY_FLAGGED
                else:
                    fieldArray[mine[1]][mine[0]] = EXPLOSION

        elif ("game_dig" in sys.argv[1]) and (MYSTERY in fieldArray[selectedY][selectedX]):
            
            # Stack-based flood fill with numbered tiles at edges
            deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            toSet = set()
            toSet.add((selectedX, selectedY))

            while len(toSet) > 0:
                cur = toSet.pop()

                if MYSTERY not in fieldArray[cur[1]][cur[0]] or list(cur) in mines:
                    continue

                numAdjacentMines = getNumAdjacentMines(cur[0], cur[1], mines)
                fieldArray[cur[1]][cur[0]] = ADJACENT[numAdjacentMines]

                for delta in deltas:
                    newPoint = (cur[0] + delta[0], cur[1] + delta[1])
                    if isValid(newPoint[0], newPoint[1]) and numAdjacentMines == 0:
                        toSet.add(newPoint)

            # Check for game win, specifically that the player hasn't missed a spot
            gameOver = True
            for rowNum in range(GRID_HEIGHT):
                for columnNum in range(GRID_WIDTH):
                    if (MYSTERY or FLAG) in fieldArray[rowNum][columnNum] and [columnNum, rowNum] not in mines:
                        gameOver = False

        # Unlink - we don't want anything clickable after game over
        if gameOver:
            unlinkCell = lambda cellContents: MYSTERY if (MYSTERY in cellContents) else (FLAG if FLAG in cellContents else cellContents)
            for rowNum, rowArray in enumerate(fieldArray):
                fieldArray[rowNum] = list(map(unlinkCell, rowArray))
              
        overwriteAndClose(file, json.dumps(fieldArray))

        # Render grid to README or archive file
        filenameToWrite = "prev-game.md" if gameOver else "README.md"
        file = open("template/" + filenameToWrite, "r", encoding="utf8")
        table = file.read()
        file.close()

        table = table.replace("FIELD_GOES_HERE", toMarkdown(fieldArray))
        file = open(filenameToWrite, "r+", encoding="utf8")
        overwriteAndClose(file, table)

        # Reset the field to an empty grid
        if gameOver:
            copyfile("template/field.json", "field.json")
            copyfile("template/mines.json", "mines.json")

            file = open("template/field.json", "r", encoding="utf8")
            markdown = toMarkdown(json.load(file))
            file.close()

            file = open("template/README.md", "r", encoding="utf8")
            markdown = file.read().replace("FIELD_GOES_HERE", markdown)
            file.close()

            file = open("README.md", "w", encoding="utf8")
            file.write(markdown)
            file.close()

            actionsEnv = "encrypt=true"
            
        actionsEnv += "\noutput_file=" + filenameToWrite + "\ndone=ok"

    # We can attribute some users to improper user input, others not
    except json.JSONDecodeError as jsonError:
        if jsonError.doc == sys.argv[2]:
           actionsEnv += "\ndone=bad_input"
        else:
            raise jsonError
    
    except ValueError as valueError:
        if(str(valueError) == "Invalid input"):
            actionsEnv += "\ndone=bad_input"
        else:
            raise valueError

    except Exception as error:
        sys.stderr.write(format_exc())
        actionsEnv += "\ndone=error"

    finally:

        # For GitHub Actions, this (stdout) gets redirected to a special env file
        print(actionsEnv)
        sys.exit(0)

if __name__ == "__main__":
    main()

# new fcns:
# funExtractColumn; extracts a column from a 2D array and returns it
# funSaveDataToCSV; accepts a matrix & locale to which the data structure will be saved in as a .csv
    # provides both overwriting and appending capability
# funLoadDataFromCSV; transfers data from .csv to a 2D array

# Objective: the fcn 'funExtractColumn'

# Input: 1) the column to be extracted & 2) matrix from which it will be extracted
# Output 1) the column

def funExtractColumn(kCol, matrixInput):
    # 1. Init counter k1
    k1 = 0

    # 2. Define temp array to hold kth column
    arrayOutput = [0 for x in range(len(matrixInput))]

    # 3. Save only appropriate values from rows to this
    # array. Increment counter as needed.
    while k1 < len(matrixInput):
        arrayOutput[k1] = matrixInput[k1][kCol]
        k1 += 1

    # 4. Return
    return arrayOutput

# Objective. 'funSaveDataToCSV'
# Input 1) the matrix to be saved, 2) the path to which it will be saved.
# 3) an indicator of whether append or write mode will be used
# Output: n/a

def funSaveDataToCSV(matrixInput, strFilePath, strAppendOrWrite):
    # 1. Define 2 vals based on whether 'write'/'append' mode is used.
    # one is 'nCols', or the number of columns.
    # another is 'intFirstNewRow', or the 1st row to which new data is saved
    # the ways in which these vals are defined depends on mode.
    if strAppendOrWrite == 'append':
        # 2. Load existing data
        matrixLoadedData = funLoadDataFromCSV(strFilePath)

        # 3. Define 'nCols' as larger of two following vals: 1) num of existing columns
        # 2) num of coulmns of matrixInput

        if len(matrixInput[0]) >= len(matrixLoadedData[0]):
            # 4. Define 'nCols' as larger val
            nCols = len(matrixInput[0])

        else:
            # 5. as larger val
            nCols = len(matrixLoadedData[0])
        
        # 6. Define 1st new row of data to be appended
        intFirstNewRow = len(matrixLoadedData)
    # 7. Define vals alternatively if 'write mode' is used
    else:
        # 8. define nCols based on width of matrixInput
        nCols = len(matrixInput[0])

        # 9. Define intFIrstNewRow as 0 b/c no existing data is used
        intFirstNewRow = 0

    # 10. Init the matrix (matrixDataToSave) that will hold all results
    # num of rows is equal to:
        # a) if 'append', num of rows in existing + num of rows in matrixInput
        # b) if 'write', num of rows in matrixInput
    
    if strAppendOrWrite == 'append':
        # 11. define nRows
        nRows = intFirstNewRow+len(matrixInput)

        # 12. Init matrix w/ consideration of existing vals
        matrixDataToSave = [[0 for x in range(nCols)] for x in range(nRows)]
        # above is syntax for init array

    else:
        # 13. Define nRows
        nRows = len(matrixInput)

        # 14. Init matrix
        matrixDataToSave = [[0 for x in range(nCols)] for x in range(nRows)]
    
    #20. Transfer vals from matrixLoadedData to matrixDataToSave if in append node
    if strAppendOrWrite == 'append':
        for k1 in range(0,len(matrixLoadedData)):
            for k2 in range(0,len(matrixLoadedData[0])):
                matrixDataToSave[k1][k2] = matrixLoadedData[k1][k2]

    # 21. Transfer vals from Input to DataToSave after existing vals
    for k1 in range(0,len(matrixInput)):
        for k2 in range(0,len(matrixInput[0])):
            matrixDataToSave[k1+intFirstNewRow][k2] = matrixInput[k1][k2]
    
    # 22. Open file with write access
    DataToSave = open(strFilePath, 'w')

    # 23. Cycle thru all rows of matrix where k1 = row num
    for k1 in range(0, len(matrixDataToSave)):
        #24. Cycle thru elements in k1-th row where k1 = col num
        for k2 in range(0,len(matrixDataToSave[0])):

            #25. Write each element in a matrix's row to same row
            # of txt file
            DataToSave.write(str(matrixDataToSave[k1][k2]))

            if k2 != len(matrixDataToSave[0]-1):
                #26. use the comma to separate elemnets but do not put it at
                # end of line
                DataToSave.write(',')
        # 27. Once k1-th row is complete move text file to next row as well
        DataToSave.write('\n')

    # 28. close data file
    DataToSave.close()

# Obective: fcn funLoadDataFromCSV

#Input 1) path of file to be loaded
# Output 1) a 2D array containing data from the .csv file

def funLoadDataFromCSV(strFilePath):
    # 1
    import os

    # 2. open file @ strFilePath for read only
    DataToLoad = open(strFilePath, 'r')

    #3. Init 2D array to temp store data
    arrayLoadedData = []

    #4. Init var to store num of rows in .csv file
    nRows = 0

    # 5. Null (nevermind)

    # 6. the for loop below loads every element fromt the .csv file
    # into a single array (not matrix) named arrayLoaded Data
    # again, the semicolon separator is used to signify the break between lines
    for EachLine in DataToLoad:
        #7. Split lines by semicolon separator
        tempData = EachLine.split(',')

        # 8. Strip any 'spaces' from the data. Append it to arrayLoaded Data
        for k2 in range(0,len(tempData)):
            tempData[k2] = tempData[k2].strip()
            arrayLoadedData.append(tempData[k2])
        
        #9. Once a row is complete, append the semicolon separator.
        arrayLoadedData.append(';')

        #10. Increment number of rows counter (nRows)
        nRows += 1
    # 11. Calculate index of final Col in .csv file
    IndexFinalCol = (len(arrayLoadedData)/nRows)-1

    # 12. Init a matrix of appropriate size
    matrixLoadedDataArray = [[0 for x in range(IndexFinalCol)] for x in range(nRows)]

    # 13. Define strSeperator as ';'
    strSeparator = ';'

    # 14. For loop converts the 1D array arrayLoadedData to the desired
    # 2D matrixLoadedDataArray. it parses thru every element of it
    for k1 in range(0, nRows):
        for k2 in range(0, IndexFinalCol):
            # 15. eqn below calculates appropriate index
            # for arrayLoadedDat such that the proper val is transferred
            # to matrixLoadedDataArray
            indexArray = (k1)*(IndexFinalCol+1)+k2

            # 16. The if statement below provides the user an error msg
            # if one of the semicolon seps should accidentally slip thru
            # the filtering process
            if arrayLoadedData[indexArray] == strSeparator:
                print("Error: Separator semicolon is present in matrixLoadedDataArray. Problem with indexing.")
            else:
                #17. if no seps are left, transfer val
                # to the matrixLoadedDataArray
                matrixLoadedDataArray[k1][k2] = arrayLoadedData[indexArray]

    return matrixLoadedDataArray
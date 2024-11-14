def main():
    # import appropriate libraries / modules
    import os

    # 2. Init arrays w/ info to be saved to txt file
    moduleA = ['Packet A', '1.87545', 'Packet B']
    moduleB = ['Packet C', '1.875456', 'Packet D']

    # 3. use 'realpath' cmd in 'os' library to determine lcoation
    # of the 'SampleWrite.txt' file
    # assuming that they are in the same folder
    FullPath = os.path.realpath('SampleWrite.txt')

    # 4. print path for user
    print("Data will be saved to following path: %r" % str(FullPath))

    # 5. Append 'FullPath' to the file name 'sample.txt' to create a more
    # complete file name that may be used for access.
    FilePath = '%s/SampleWrite.txt' % os.path.dirname(FullPath)

    # 6. Try to access file at 'FilePath' which is combo of 
    # 'FullPath' and 'SampleWrite.txt'

    try:
        # 7. Open the file w/ write access.
        RadioData = open(FilePath, 'w')

        # 8. Init counter k1, this will be used to index elements
        # of module A and B
        k1 = 0

        # 9. Cycle thru elements of mod A.
        while k1 < len(moduleA):
            # 10. Write info to text file.
            RadioData.write('Module A, Element %s : %s \n' % (k1, moduleA[k1]))
            k1 += 1
        
        # 11. Repeat for B.
        k1 = 0

        while k1 < len(moduleB):
            RadioData.write('Module B, Element %s : %s \n' % (k1, moduleB[k1]))
            k1 += 1

        # 12. Close file
        RadioData.close()

        # Define exceptions
    except:
        print("Cannot write to file.")

    
if __name__ == "__main__":
    main()

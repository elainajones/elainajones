# CPP notes

## About

C++ motes written by Elaina Jones

## Contents

- [About CPP](#about-cpp)
- [Header file libraries](#header-file-libraries)
- [Comments](#comments)
- [Functions](#functions)
- [Objects](#objects)
    - [cout](#cout)
- [Variables](#variables)
    - [Variable types](#variable-types)
    - [Variable declaration](#variable-declaration)
    - [Variable identifiers](#variable-identifiers)
- [Data types](#data-types)
- [Operators](#operators)


## About CPP

- Cross platform language for high performance applications.
- Developed by Bjarne Stroustrup as an extention to the C language.
- Supports high level of control over system resources and memory.
- Supports classes and objects while C does not, extending its use  
  for object oriented programming.


## Header file libraries

Referenced with `#include` at the top of the file to add extra  
functionality to C++ programs.  
  
The following will almost always appear in programs:  
```cpp
#include <iostream>
using namespace std

//code
```
  
List of header file libraries:  
- `<iostream>`
    - Adds functionality for input and output objects, such as `cout`.
    - `using namespace std`


## Comments

- `//`
    - Single line comments.
- `/*` and `*/`.
    - Multi line comments.


## Functions

- Declared with data type of the returned value (e.g. `int`).
- Code inside curly braces will be executed.
- Always returns a value or `return 0`.
- Lines end with `;` to denote the end of line.
  
Example:  
```cpp
int main() {
    cout << "Hello World!";
    return 0;
}
```

## Objects

### cout

The `cout` object ("see out"), together with the `<<` operator, is used to  
output values/print text.  
  
Example:  
```cpp
int main() {
    cout << "Hello World!";
    cout << "I am learning C++";
    return 0;
}
```  
  
- `cout` does not insert a new line at the end of the output.  
  - The `\n` character will create a new line.
  - The `end1` manipulator will insert a new line.  
    (i.e. `cout << "foo bar" << end1;`)

### cin

`cin` is a predefined variable that reads data from the keyboard with  
extraction operator (`>>`).  
  
Example:
```cpp
int x; 
cout << "Type a number: "; // Type a number and press enter
cin >> x; // Get user input from the keyboard
cout << "Your number is: " << x; // Display the input value 
```


## Variables

### Variable types:
- `int`
    - Stores integers (whole numbers), without decimals (e.g. 123).
- `double`
    - Stores floating point numbers, with decimals (e.g. 19.99).
- `char`
    - Stores single characters (e.g. 'a', 'B').
    - `char` values are surrounded by single quotes.
- `string`
    - Stores text (e.g. "Hello World").
    - `string` values are surrounded by double quotes.
`bool`
    - Stores values with two states: `true` or `false`.
  

### Variable declaration

One value to one variable:  
`type variableName = value;`  
  
Many variables:  
`int x = 5, y = 6, z = 50;`  
  
One value to multiple variables:  
```cpp
int x, y, z;
x = y = z = 50;
```


### Variable identifiers

- Can contain letters, digits, and underscores.
- Must begin with a leter or an underscore.
- Names are case sensitive.
- Cannot contain whitespace or special characters.
- Reserved words (C++ keywords, such as `int`) cannot be used as names.


### Constant variables

- Variables declared with the `const` keyword will be unchangeable  
  and read-only.  
- It is a good practive to always declare variables as constant when  
  values are unlikely to change.
  
Example:  
```cpp
const int minutesPerHour = 60;  // Value will always be 60
minutesPerHour = 10;  // error: assignment of read-only variable.
```


## Data types

- `bool`
    - 1 byte.
    - Stores `true` or `false` values.
- `char`
    - 1 byte.
    - Stores a single character/letter/number, or ASCII values.
    - Surrounded by single quotes.
- `int`
    - 2-4 bytes.
    - Stores whole numbers, without decimals.
- `float`
    - 4 bytes.
    - Stores fractional numbers, containing one or more decimals.  
      Sufficient for storing  7 decimal digits.
    - Can also be a scientific number with an "e" to indicate power  
      of 10 (e.g. `35e3`).
- `double`
    - 8 bytes.
    - Stores fractional numbers, containing one or more decimals.
      Sufficient for storing 15 decimal digits.
- `string`
    - Stores text.
    - Surrounded by double quotes.


## Operators

- `+`
    - Addition.
- `-`
    - Subtraction.
- `*`
    - Multiplication.
- `/`
    - Division.
- `%`
    - Modulus.
    - Returns the division remainder.
- `++`
    - Increment.
    - Increases the value of a variable by 1.
- `--`
    - Decrement.
    - Decreases the value of a variable by 1.
- `=`
    - Assignment.
- `+=`
    - Adds to the assigned value (e.g. `x = x + y`).



#!/usr/bin/env python3

import os
import re
import argparse
from enum import Enum

binary_opcode = {
    "ADD":  "00001",
    "SUB":  "00010",
    "MUL":  "00011",
    "DIV":  "00100",
    "ADDI": "00101",
    "SUBI": "00110",
    "MULI": "00111",
    "DIVI": "01000",
    "AND":  "01001",
    "OR":   "01010",
    "XOR":  "01011",
    "ANDI": "01100",
    "ORI":  "01101",
    "XORI": "01110",
    "SLT":  "01111",
    "SLTI": "10000",
    "LW":   "10001",
    "SW":   "10010",
    "BEQ":  "10011",
    "BNQ":  "10100",
    "JR":   "10101",
    "J":    "10110"
}

binary_registers_names = {
    "$zero": "0000",
    "$rd":   "0001",
    "$rs":   "0010",
    "$t0":   "0011",
    "$t1":   "0100",
    "$t2":   "0101",
    "$t3":   "0110",
    "$lo":   "0111",
    "$hi":   "1000",
}

class GenerationMode(Enum):
    LOGISIM = 0
    BINARY  = 1

def fill_string_into(string: str, into: int, by: str, to_right: bool = True) -> str:
    if to_right:
        while len(string) < into:
            string = string + by
    else:
        while len(string) < into:
            string = by + string
    return string

def format_instruction(instruction: str) -> str:
    instruction = fill_string_into(instruction, 29, "0")
    if generation_mode == GenerationMode.LOGISIM:
        instruction = hex(int(instruction, base=2)).removeprefix("0x")
    else:
        instruction = instruction[:5] + " " + instruction[5:9] + " " + instruction[9:13] + " " + instruction[13:]
    return instruction

def check_register(reg_name: str) -> None:
    if not reg_name in binary_registers_names.keys():
        raise ValueError(f"Unknown register name: {reg_name}")
    
def check_immediate_operand(op: str) -> str:
    try:
        op_bin = bin(int(op)).removeprefix("0b")
    except ValueError:
        raise ValueError(f"Immediate value must be a number or label, got: {op}")
    
    if len(op_bin) > 16:
        raise ValueError(f"Immediate value: {op}, exceeded 16 bit long")
    
    return op_bin

arg_parser = argparse.ArgumentParser(description="A simple MIPS assembler")
arg_parser.add_argument("source", help="The source file code to assemble")
arg_parser.add_argument("-o", dest="outfile", required=True, help="Specify generated machine code file path")
switches = arg_parser.add_mutually_exclusive_group()
switches.add_argument("-l", action="store_true", default=True, required=False, help="Generate machine code for Logisim")
switches.add_argument("-b", action="store_true", required=False, help="Generate line-by-line binary machine code")
args = arg_parser.parse_args()

generation_mode = GenerationMode.BINARY if args.b else GenerationMode.LOGISIM
out_file_path = getattr(args, "outfile")
source_file = open(os.path.join(os.path.dirname(__file__), getattr(args, "source")), "r")
source_code = source_file.read(100 * 2 ** 20)
source_file.close()

labels_directory = {}
generated_code_instructions = []
source_code = re.sub(r";.*", "", source_code)
source_code = re.sub(r"\n\s*\n", '\n', source_code)
source_code = source_code.strip()

nline = 1
instructions = []
for line in source_code.splitlines():
    line = line.strip()
    line = re.sub(r" {2,}", " ", line)
    if re.fullmatch(r"\w+:.*", line) == None: # checking if label does not exist
        line = "    : " + line

    label, instruction = line.split(':')
    label = label.strip()

    if len(label) > 0:
        if label in labels_directory.keys():
            raise ValueError(f"Cannot redefine labels for label: '{label}'")
        else:
            labels_directory[label] = nline

    instruction = instruction.strip()
    instruction = re.sub(r",", "", instruction)

    if len(instruction) < 1:
        continue

    instructions.append(instruction)
    nline += 1

for nins in range(len(instructions)):
    instruction = instructions[nins]
    generated_instruction = None
    opcode, *operands = instruction.split(" ")

    if len(operands) > 3:
        raise ValueError(f"Invalid number of operands for instruction: '{opcode.upper()}'")

    match opcode.upper():
        case "ADD" | "SUB" | "MUL" | "AND" | "OR" | "XOR" | "SLT":
            if len(operands) < 3:
                raise ValueError(f"'{opcode.upper()}' instruction needs exatly 3 operands")
            
            op1, op2, op3 = operands
            for op in (op1, op2, op3):
                check_register(op)
            
            generated_instruction = binary_opcode[opcode.upper()] + binary_registers_names[op1.lower()] + binary_registers_names[op2.lower()] + binary_registers_names[op3.lower()]

        case "DIV":
            if len(operands) > 2:
                raise ValueError("'DIV' instruction needs exactly 2 operands")
            
            op1, op2 = operands

            for op in (op1, op2):
                check_register(op)

            generated_instruction = binary_opcode[opcode.upper()] + "0111" + binary_registers_names[op1.lower()] + binary_registers_names[op2.lower()]

        case "ADDI" | "SUBI" | "MULI" | "ANDI" | "ORI" | "XORI" | "SLTI":
            op1, op2, op3 = operands
            for op in (op1, op2):
                check_register(op)
            
            op3_bin = check_immediate_operand(op3)
            op3_bin = fill_string_into(op3_bin, 16, "0", to_right=False)
            generated_instruction = binary_opcode[opcode.upper()] + binary_registers_names[op1.lower()] + binary_registers_names[op2.lower()] + op3_bin
        
        case "DIVI":
            if len(operands) > 2:
                raise ValueError("'DIVI' instruction needs exactly only 2 operands")
            
            op1, op2 = operands
            check_register(op1)
            op2_bin = check_immediate_operand(op2)
            op2_bin = fill_string_into(op2_bin, 16, "0", to_right=False)
            generated_instruction = binary_opcode[opcode.upper()] + "0111" + binary_registers_names[op1.lower()] + op2_bin
            
        case "LW" | "SW":
            op1, tmp = operands
            m2, m3 = re.search(r"^\d", tmp), re.search(r"\$\w+", tmp)
            if m2 and m3:
                op2, op3 = m2.string[m2.span()[0]:m2.span()[1]], m3.string[m3.span()[0]:m3.span()[1]]
                for op in (op1, op3):
                    check_register(op)
            
                op2_bin = check_immediate_operand(op2)
                op2_bin = fill_string_into(op2_bin, 16, '0', to_right=False)
                generated_instruction = binary_opcode[opcode.upper()] + binary_registers_names[op1.lower()] + binary_registers_names[op3.lower()] + op2_bin

            else:
                raise ValueError("There was an error while parsing the 'LW' instruction")
            
        case "BEQ" | "BNQ":
            op1, op2, op3 = operands

            for op in (op1, op2):
                check_register(op)
            
            if op3.isidentifier():
                if op3 in labels_directory.keys():
                    op3 = str(abs(labels_directory[op3] - (nins + 1)))
                else:
                    raise ValueError(f"No defined label: '{op3}'")

            op3_bin = check_immediate_operand(op3)
            op3_bin = fill_string_into(op3_bin, 16, '0', to_right=False)
            generated_instruction = binary_opcode[opcode.upper()] + binary_registers_names[op1.lower()] + binary_registers_names[op2.lower()] + op3_bin

        case "JR":
            if len(operands) > 1:
                raise ValueError("JR instruction needs exactly one operand")
            
            op1, *_ = operands
            check_register(op1)
            generated_instruction = binary_opcode[opcode.upper()] + "0000" + binary_registers_names[op1.lower()] + "0" * 16

        case "J":
            if len(operands) > 1:
                raise ValueError("JR instruction needs exactly one operand")
            
            op1, *_ = operands
            if op1.isidentifier():
                if op1 in labels_directory.keys():
                    op1 = str(labels_directory[op1])
                else:
                    raise ValueError(f"No defined label: '{op1}'")

            op1_bin = check_immediate_operand(op1)
            op1_bin = fill_string_into(op1_bin, 16, "0", to_right=False)
            generated_instruction = binary_opcode[opcode.upper()] + "0" * 8 + op1_bin

        case _:
            raise ValueError(f"Invalid instruction name: '{opcode}'")
    
    generated_code_instructions.append(format_instruction(generated_instruction))

with open(out_file_path, 'w') as out_file:
    match generation_mode:
        case GenerationMode.LOGISIM:
            out_file.write("v2.0 raw\n" + "0000000 " + " ".join(generated_code_instructions) + '\n')
        case GenerationMode.BINARY:
            out_file.write("\n".join(generated_code_instructions) + '\n')

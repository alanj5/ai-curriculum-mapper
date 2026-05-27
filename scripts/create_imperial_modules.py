#!/usr/bin/env python3
"""Create Imperial College Computing Department module JSON files.

Data sourced from https://www.imperial.ac.uk/engineering/departments/computing/
current-students/courses/<CODE>/ (accessed May 2026).

Level convention:
  40xxx → level 1 (Year 1 UG)
  50xxx → level 2 (Year 2–3 UG)
  60xxx → level 3 (Year 4 MEng / optional)
"""

import json
import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent
RAW_MODULES = BASE / "data" / "raw" / "modules"
MIT_FALLBACK = RAW_MODULES / "MIT_OCW_fallback"
IMPERIAL_DIR = RAW_MODULES / "imperial"

MODULES = [
    {
        "code": "IC40001",
        "title": "Introduction to Computer Systems",
        "level": 1,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module examines fundamental principles and devices used in the design "
            "of digital computers, and the way in which primitive control logic can be "
            "organised to construct a programmable machine. Students study number "
            "representations, Boolean algebra, combinatorial and sequential logic, "
            "and progress to ALU and CPU design."
        ),
        "learning_objectives": [
            "Explain combinatorial circuit design and synchronous sequential circuit design",
            "Design a CPU using Boolean algebra and functional design",
            "Describe basic CPU architecture, its components, and hardware control mapping",
            "Compare and use different number representations",
        ],
        "topics": [
            "Number representations and computer arithmetic",
            "Boolean algebra",
            "Combinatorial logic functions",
            "Principles of semiconductor devices and logic gates",
            "Adders, subtractors, and multipliers",
            "Bistable storage devices",
            "Flip-flop design",
            "Registers",
            "Multiplexers and decoders",
            "Counters",
            "Finite state machines",
            "Static and dynamic RAM",
            "Register transfer descriptions",
            "ALU and CPU design",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40005",
        "title": "Introduction to Computer Architecture",
        "level": 1,
        "credits": 8,
        "prerequisites": ["IC40001"],
        "description": (
            "Students develop a fundamental understanding of the organisation and "
            "operation of a computer system with emphasis on how high-level language "
            "programs are represented and executed at an architectural level. Topics "
            "include ISA design, CISC vs RISC, assembler programming, and the memory "
            "hierarchy."
        ),
        "learning_objectives": [
            "Describe the basic organisation of a computer",
            "Explain different representations used for instructions, numbers and text",
            "Show how machine code instructions are executed by a computer",
            "Compare different implementations of a computer's control unit",
            "Explain program behaviour by reading the binary representation of machine code",
            "Translate high-level program fragments into assembler code",
            "Explain the effect that memory hierarchy has on a program's execution time",
            "Estimate the performance of a program on a given computer",
        ],
        "topics": [
            "Basic organisation of a computer",
            "Representations for instructions, numbers and text",
            "Translation of high-level programs into instructions",
            "Instruction execution",
            "Implementation choices of the control unit",
            "CISC and RISC Instruction Set Architecture",
            "Assembler programming",
            "Memory organisation and concepts of spatial and temporal locality",
            "Memory hierarchy",
            "Cache memory",
            "Performance estimation",
            "Amdahl's Law",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40007",
        "title": "Introduction to Databases",
        "level": 1,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module covers modern database system structures, relational database "
            "modelling, normalisation, SQL query design, and contemporary database "
            "technologies. Students understand the separation of physical and logical "
            "models and transaction management."
        ),
        "learning_objectives": [
            "Compare and contrast different database models and supporting architectures",
            "Model information in a relational system",
            "Optimise a relational schema and demonstrate correctness of optimisations",
            "Design relational queries and write SQL queries",
            "Set up a database, implement a schema as well as the queries",
            "Explain the benefits of separating physical and logical models",
        ],
        "topics": [
            "Database systems",
            "Relational model",
            "Database design",
            "Entity-relationship modelling",
            "Functional dependencies, keys and normal forms",
            "Relational database languages",
            "Relational algebra",
            "SQL",
            "Views integrity and security",
            "Transaction management and concurrency",
            "Normalisation",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40008",
        "title": "Graphs and Algorithms",
        "level": 1,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module offers students opportunities to prove mathematical properties "
            "of graphs, explore classical algorithms for graphs and trees, design sorting "
            "and searching algorithms, determine algorithm time complexity, and study the "
            "complexity classes P and NP along with NP-completeness."
        ),
        "learning_objectives": [
            "Prove basic properties of graphs",
            "Describe and establish the correctness of fundamental algorithms in computing",
            "Analyse the time complexity of an algorithm",
            "Explain the complexity classes P and NP and the P=NP problem",
            "Determine to which complexity class a computational problem belongs",
        ],
        "topics": [
            "Graphs and graph representations",
            "Graph traversal algorithms",
            "Breadth-first search",
            "Depth-first search",
            "Minimum spanning trees",
            "Shortest paths",
            "Dijkstra's algorithm",
            "Dynamic programming",
            "Divide and conquer",
            "Searching and sorting algorithms",
            "Algorithm analysis",
            "Time complexity",
            "Recurrence relations",
            "Master Theorem",
            "Decision trees",
            "Complexity classes P and NP",
            "NP-completeness",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40009",
        "title": "Computing Practical 1",
        "level": 1,
        "credits": 16,
        "prerequisites": [],
        "description": (
            "This module develops practical programming skills across multiple paradigms "
            "including functional, object-oriented, procedural, and systems programming. "
            "Students build web development skills, use version control, conduct basic "
            "research into computing topics including ethics, and develop technical "
            "communication and presentation abilities."
        ),
        "learning_objectives": [
            "Demonstrate proficiency in programming languages from three of the major paradigms",
            "Develop working solutions to well-specified programming problems of small to medium size",
            "Create a website that meets stakeholder needs",
            "Use core software development tools effectively including those for version control",
            "Undertake basic research into computing topics including those related to computing ethics",
            "Write short technical documentation demonstrating proficiency in scientific communication",
            "Deliver short oral presentations summarising practical project work and research findings",
            "Operate effectively as a member of a group to produce deliverables that meet set criteria",
        ],
        "topics": [
            "Functional programming in Haskell",
            "Functional and procedural programming in Kotlin",
            "Object-oriented programming in Kotlin and Java",
            "Assembler programming",
            "Programming in C",
            "Web development using HTML, CSS and JavaScript",
            "Computer systems project",
            "Version control",
            "Introduction to research methods",
            "Ethics in computing",
            "Academic writing",
            "Oral presentation skills",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40012",
        "title": "Logic and Reasoning",
        "level": 1,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module provides opportunities to study the syntax, semantics and proof "
            "systems of first-order logic, convert natural language to formal logic "
            "representations, apply semantic methods for validating arguments and logical "
            "equivalences, use logic for analysing program behaviour via conditions and "
            "invariants, and apply induction techniques to recursive program reasoning."
        ),
        "learning_objectives": [
            "Recall the definitions of the classical logics and logical systems",
            "Read, parse and evaluate logical formulas",
            "Formalise English text into first-order logic, and vice versa",
            "Construct proofs using proof systems presented",
            "Provide suitable pre, post and mid conditions and loop variants and invariants to program fragments",
            "Use structural induction to reason about the correctness of functional programs",
        ],
        "topics": [
            "Propositional logic",
            "First-order logic",
            "Syntax and semantics of logical formulas",
            "Proof systems",
            "Formula equivalences",
            "Soundness and completeness",
            "Induction",
            "Program reasoning",
            "Pre-conditions and post-conditions",
            "Loop invariants",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40016",
        "title": "Calculus",
        "level": 1,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module covers the calculus needed for many applications of computing "
            "such as graphics, vision, robotics, operations research and statistical "
            "machine learning. Topics include sequences and series convergence, "
            "multivariate calculus, and optimisation."
        ),
        "learning_objectives": [
            "Establish convergence or divergence of sequences and series and determine limit values",
            "Derive Maclaurin and Taylor series and determine radius of convergence",
            "Find approximations from below and above to the value of an integral",
            "Find the minima, maxima and saddle points of multivariate functions",
            "Find approximations to roots of multivariate functions",
            "Compute integrals with respect to cylindrical and spherical coordinate systems",
        ],
        "topics": [
            "Ordering and supremum of real numbers",
            "Sequences, series and convergence",
            "Limits of functions and continuity",
            "Intermediate value theorem",
            "Differentiation and its properties",
            "Mean value theorem",
            "Riemann integral",
            "Trapezium rule",
            "Uniform convergence and power series",
            "Metric spaces",
            "Contraction mapping theorem",
            "Multivariate differential calculus",
            "Partial derivatives",
            "Hessian and Taylor series",
            "Extrema of scalar fields",
            "Newton's method",
            "Vector valued functions",
            "Jacobian matrix",
            "Cylindrical and spherical coordinate systems",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40017",
        "title": "Linear Algebra",
        "level": 1,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module covers linear algebra which underpins many applications of "
            "computing involving analysis of aggregated data in vector or matrix form. "
            "Applications span graphics, robotics, performance engineering, operations "
            "research, and statistical machine learning."
        ),
        "learning_objectives": [
            "Solve systems of linear equations using Gaussian elimination",
            "Determine matrices representing linear mappings",
            "Compute matrix rank",
            "Compute eigenvalues and eigenvectors for simple matrices and explain their application",
            "Define projections and rotations in matrix form",
            "Find the spectral decomposition of real symmetric matrices",
        ],
        "topics": [
            "Vectors and matrices",
            "Solution of linear systems of equations",
            "Gaussian elimination",
            "Vector spaces",
            "Linear transformations and matrix representation",
            "Change of basis",
            "Orthonormal bases and Gram-Schmidt",
            "Rank and Nullity Theorem",
            "Scalar products",
            "Orthogonal subspaces",
            "Introduction to linear regression",
            "Eigenvalue and eigenvector problem",
            "Determinants and their properties",
            "Diagonalisability of matrices",
            "Cayley-Hamilton theorem",
            "Projections",
            "Rotation matrices",
            "Symmetric matrices",
            "Spectral decomposition",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40018",
        "title": "Discrete Mathematics, Logic and Reasoning",
        "level": 1,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module demonstrates how discrete mathematics and logic can be used to "
            "describe and reason about computational structures and systems. It establishes "
            "foundations for computing topics including hardware design, algorithm analysis, "
            "and program verification, with emphasis on proof techniques for verifying "
            "program and system specifications."
        ),
        "learning_objectives": [
            "Construct various mathematical proofs using informal and formal reasoning",
            "Define properties of fundamental discrete structures like sets, relations, and functions",
            "Read, parse, and evaluate logical formulas",
            "Formalise English statements into logic",
            "Use logic to specify desired system, program, or algorithm properties",
            "Apply induction to reason about recursive program and data structure correctness",
            "Provide suitable pre-, post-, and mid-conditions and invariants for imperative programs",
            "Use logic to reason about imperative program correctness",
        ],
        "topics": [
            "Logical connectives",
            "Proof methods",
            "Sets, relations and functions",
            "Countability",
            "Orderings",
            "Induction",
            "Inductive reasoning for recursive programs and data types",
            "Logic formalization syntax and semantics",
            "Validity and satisfiability",
            "Equivalence",
            "Logical proof systems",
            "Soundness and completeness",
            "Pre-conditions, post-conditions, and mid-conditions",
            "Loop invariants and variants",
            "Logical reasoning applied to imperative programs",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50001",
        "title": "Algorithm Design and Analysis",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40008"],
        "description": (
            "This module explores foundational algorithmic design paradigms and their "
            "practical applications. Students engage with quantitative algorithm analysis, "
            "apply techniques to novel problems, and develop structured approaches to "
            "computational problem-solving through mathematical abstraction and implementation."
        ),
        "learning_objectives": [
            "Compare, characterise and evaluate different implementations of basic algorithms",
            "Analyse algorithms using quantitative evaluation",
            "Formulate algorithmic abstractions of computational problems",
            "Design and implement efficient algorithms for practical and unseen problems",
            "Specify which algorithms can be applied to which classes of problems",
        ],
        "topics": [
            "Quantitative analysis of algorithms and growth order",
            "Asymptotic notation",
            "Divide and conquer",
            "Dynamic programming",
            "Greedy algorithms",
            "Randomised algorithms",
            "Advanced graph algorithms",
            "Network flow",
            "String processing algorithms",
            "Algorithm correctness and invariants",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50002",
        "title": "Software Engineering Design",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40009"],
        "description": (
            "This module examines design decision impacts on software system flexibility, "
            "maintainability, and costs. Students practice refactoring techniques, automated "
            "testing, design pattern selection, and architectural approaches suitable for "
            "various problems. The course emphasises technical practices within iterative "
            "software delivery contexts."
        ),
        "learning_objectives": [
            "Identify and describe design patterns, their addressed problems, and trade-offs",
            "Make informed engineering decisions to minimise change costs",
            "Implement common design structures for software applications",
            "Construct automated tests through test-driven development",
            "Perform refactoring operations using appropriate tools",
            "Critique design qualities of existing codebases",
        ],
        "topics": [
            "Test-driven development",
            "Refactoring",
            "Mock objects",
            "Encapsulation and the Law of Demeter",
            "Design patterns for re-use and extensibility",
            "Code quality metrics",
            "Design patterns for data processing and concurrency",
            "Design patterns for object creation and dependency management",
            "Interactive GUI applications",
            "Patterns for system integration",
            "Patterns for distribution",
            "Web applications, REST and web services",
            "Agile development practices",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50003",
        "title": "Models of Computation",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40012"],
        "description": (
            "This module concentrates on formal descriptions of computational behaviour "
            "covering operational semantics of programming languages and foundational "
            "definitions of algorithms. Topics include Turing machines, lambda calculus, "
            "register machines, the halting problem, and the Church-Turing thesis."
        ),
        "learning_objectives": [
            "Provide formal descriptions of programming language behaviour across multiple styles",
            "Prove properties of such languages",
            "Supply several formal definitions of algorithm",
            "Connect algorithmic definitions with computable functions",
        ],
        "topics": [
            "Operational semantics for WHILE language",
            "Programming language properties: confluence, totality",
            "Inductive proofs for language extensions",
            "Featherweight semantics for alternative programming styles",
            "Register machines and universal register machines",
            "Computable functions",
            "Halting problem",
            "Turing machines",
            "Lambda calculus",
            "Church-Turing thesis",
            "Computability theory",
            "Formal language theory",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50004",
        "title": "Operating Systems",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40001", "IC40005"],
        "description": (
            "This module develops understanding of core operating system abstractions and "
            "explores implementation trade-offs across modern operating system subsystems. "
            "Students investigate mechanisms and policies for resource management, process "
            "isolation, scheduling, virtual memory, and file systems."
        ),
        "learning_objectives": [
            "Distinguish between different styles of operating system design",
            "Explain main principles behind resource abstraction and resource management",
            "Explain principles behind process isolation and process and thread models",
            "Explain scheduling problems and inter-process communication mechanisms",
            "Identify concurrency-related problems and explain synchronisation mechanisms",
            "Evaluate security risks and the OS role in establishing security",
        ],
        "topics": [
            "Operating system kernel organisation",
            "Processes and threads",
            "Process and thread abstractions",
            "Inter-process synchronisation mechanisms",
            "Semaphores and mutexes",
            "Concurrency control",
            "Scheduling algorithms",
            "Round-robin scheduling",
            "Priority scheduling",
            "Virtual memory",
            "Paging",
            "Demand paging",
            "Page replacement",
            "Device and disk management",
            "File system abstractions",
            "Journaling file systems",
            "Deadlock",
            "Race conditions",
            "Memory management",
            "Basic security concepts",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50005",
        "title": "Networks and Communications",
        "level": 2,
        "credits": 8,
        "prerequisites": [],
        "description": (
            "This module examines foundational networking principles, OSI and TCP/IP "
            "architectural models, network design methodologies based on specific "
            "requirements, and basic computer security concepts. Students learn to "
            "calculate network metrics and analyse security risks."
        ),
        "learning_objectives": [
            "Define and classify major concepts in computer networking",
            "Design a computer network based on given requirements",
            "Calculate important network metrics",
            "Identify and analyse potential security risks",
        ],
        "topics": [
            "Introduction to networking concepts",
            "OSI model",
            "TCP/IP protocol stack",
            "Application layer protocols",
            "Transport layer",
            "TCP and UDP",
            "Network layer",
            "IP addressing and routing",
            "Data link layer",
            "Physical layer",
            "Network security",
            "Cryptography basics",
            "Client/server programming",
            "Network design",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50008",
        "title": "Probability and Statistics",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40016"],
        "description": (
            "This module develops probability theory for modelling uncertainty and designing "
            "probabilistic models for prediction. It emphasises mathematical foundations "
            "combined with practical application. Topics include random variables, "
            "hypothesis testing, confidence intervals, and Markov chains."
        ),
        "learning_objectives": [
            "Describe probability notions in terms of sample spaces",
            "Define and use random variables",
            "Design simple probability models and estimate parameters from data",
            "Construct confidence intervals",
            "Perform hypothesis tests and draw scientific conclusions",
            "Apply estimation and testing procedures",
        ],
        "topics": [
            "Foundations of probability theory",
            "Discrete random variables and their probability distributions",
            "Poisson processes",
            "Continuous random variables and their probability distributions",
            "Central Limit Theorem",
            "Joint random variables",
            "Estimation",
            "Fundamentals of simulation",
            "Markov chains",
            "Hypothesis testing",
            "Confidence intervals",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50009",
        "title": "Symbolic Reasoning",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40012"],
        "description": (
            "This module covers the foundations of symbolic reasoning: SAT solving, "
            "logic programming, answer set programming, and SMT solving. Students develop "
            "practical skills to solve real-world problems in program reasoning and "
            "symbolic artificial intelligence."
        ),
        "learning_objectives": [
            "Describe theoretical foundations of Boolean Satisfiability (SAT) and SMT solving",
            "Implement algorithms for SAT solving",
            "Encode problems in SMT form and solve them using state-of-the-art SMT solvers",
            "Explain the theoretical foundations of logic programming",
            "Apply resolution as an inference system for logic programming",
            "Encode problems using Answer Set Programming and solve them using ASP solvers",
        ],
        "topics": [
            "Boolean Satisfiability (SAT)",
            "NP-completeness of SAT",
            "DPLL algorithm",
            "Conflict-driven clause learning (CDCL)",
            "Knowledge representation",
            "Logic programming",
            "Herbrand models",
            "Answer Set Programming (ASP)",
            "SLD resolution",
            "SLDNF resolution",
            "Satisfiability Modulo Theories (SMT)",
            "First-order theories",
            "Decidability",
            "Formal verification",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50010",
        "title": "Designing for Real People",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40009"],
        "description": (
            "Students apply software engineering techniques to develop a substantial "
            "web-based or mobile application addressing authentic problems. The coursework "
            "emphasises Human Centred Design (HCD) principles alongside relevant legal "
            "frameworks governing computing applications."
        ),
        "learning_objectives": [
            "Describe and discuss the concepts involved in Human-Centred Design and agile software development",
            "Conduct research into a real-world problem following HCD principles",
            "Design, engineer and deploy a web-based or mobile-based application to solve a real-world problem",
            "Work effectively as part of a small group to deliver software iteratively using agile methods",
            "Report, present and demonstrate a solution and its value proposition to an interdisciplinary audience",
            "Recall relevant Computer Laws and act in a manner that demonstrates awareness and conformity",
        ],
        "topics": [
            "Human-Centred Design",
            "Agile software development",
            "User research methods",
            "Prototyping and iterative design",
            "Usability testing",
            "Multi-user web application design and implementation",
            "Mobile application development",
            "Copyright and Data Protection law",
            "GDPR",
            "User interface design",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50011",
        "title": "Computational Techniques",
        "level": 3,
        "credits": 8,
        "prerequisites": ["IC40016", "IC40017"],
        "description": (
            "This module covers additional mathematical topics that form prerequisites "
            "for third and fourth year modules in areas such as computer graphics, "
            "machine learning, and computational finance. Topics include advanced linear "
            "algebra, numerical methods, and optimisation techniques."
        ),
        "learning_objectives": [
            "Apply advanced linear algebra topics to machine learning and deep learning problems",
            "Understand and implement mathematical methods in image processing, graphics, and computational finance",
            "Use vector calculus to solve computational optimisation problems",
        ],
        "topics": [
            "Vector and matrix norms",
            "Generalised eigenvectors",
            "Jordan normal form",
            "Singular value decomposition (SVD)",
            "Dimensionality reduction",
            "Positive definite matrices",
            "Cholesky factorization",
            "Normal equations and least squares",
            "QR decomposition",
            "Householder transform",
            "LU decomposition",
            "Matrix conditioning",
            "Algorithm stability",
            "Iterative linear system solutions",
            "Jacobi and Gauss-Seidel methods",
            "Power method for eigenvectors",
            "Steepest descent and conjugate gradient methods",
            "Linear programming",
            "Optimisation",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50013",
        "title": "Machine Learning",
        "level": 2,
        "credits": 8,
        "prerequisites": ["IC40016", "IC40017", "IC50008"],
        "description": (
            "This module examines machine learning algorithms and their applications. "
            "The course covers supervised and unsupervised learning methodologies, model "
            "evaluation techniques, and practical implementation strategies for solving "
            "computational problems."
        ),
        "learning_objectives": [
            "Explain the strengths and weaknesses of machine learning algorithms",
            "Appraise the suitability of a machine learning algorithm to solve a given problem",
            "Provide appropriate methodologies to evaluate machine learning algorithms",
            "Implement algorithms to solve machine learning problems",
            "Develop predictive models with machine learning algorithms",
            "Apply unsupervised clustering algorithms based on machine learning",
        ],
        "topics": [
            "Machine learning concepts and types",
            "Instance based learning",
            "Inductive learning",
            "Model evaluation and comparison",
            "Cross-validation",
            "Overfitting and regularisation",
            "Neural networks",
            "Backpropagation",
            "Supervised learning",
            "Unsupervised learning",
            "Clustering algorithms",
            "K-means clustering",
            "Evolutionary algorithms",
            "Decision trees",
            "Support vector machines",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60001",
        "title": "Advanced Computer Architecture",
        "level": 3,
        "credits": 8,
        "prerequisites": ["IC40005"],
        "description": (
            "This module addresses the design of general-purpose and special-purpose "
            "processors and of parallel computer systems, spanning embedded systems "
            "through to supercomputers. Students develop understanding of high-performance "
            "and energy-efficient architecture, software performance optimisation, and "
            "contemporary architectural security."
        ),
        "learning_objectives": [
            "Justify current processor designs at various architectural levels from microarchitecture to large-scale parallel systems",
            "Evaluate design alternatives considering power and performance tradeoffs",
            "Identify architectural security hazards and vulnerabilities plus mitigation strategies",
            "Optimise application kernels to exploit architectural capabilities effectively",
        ],
        "topics": [
            "Pipelining and hazards",
            "Instruction-level parallelism",
            "Locality and caching",
            "Dynamic scheduling",
            "Tomasulo's algorithm",
            "Register renaming",
            "Software instruction scheduling",
            "Software pipelining",
            "Superscalar architectures",
            "Very long instruction word (VLIW) architectures",
            "Branch prediction",
            "Speculative execution",
            "Simultaneous multithreading",
            "Vector instruction execution",
            "Cache coherency",
            "Memory systems",
            "Compiler optimisations",
            "Graphics processors and manycore architectures",
            "Security vulnerabilities and mitigation",
            "Meltdown and Spectre",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60007",
        "title": "Theory and Practice of Concurrent Programming",
        "level": 3,
        "credits": 8,
        "prerequisites": ["IC40009", "IC50003", "IC50004"],
        "description": (
            "This course introduces contemporary concurrent programming models and "
            "addresses the complexities involved in writing correct concurrent systems. "
            "It comprises practical application of shared memory concurrency in modern "
            "languages and foundational theory including hardware memory models and "
            "synchronisation mechanisms."
        ),
        "learning_objectives": [
            "Write correct and efficient concurrent software in modern programming languages",
            "Evaluate the differences between and strengths and weaknesses of a variety of concurrency models",
            "Explain the architectural mechanisms for supporting shared memory concurrency",
            "Formalise the semantics of shared memory concurrency",
            "Specify, test and verify properties of concurrent systems using formal methods",
        ],
        "topics": [
            "Shared memory concurrent programming in C++",
            "Synchronisation using locks and atomic operations",
            "Implementation of synchronisation primitives",
            "Functional programming and concurrency",
            "Dynamic data race detection",
            "Strong and weak memory models",
            "Races, deadlocks, livelocks, and progress guarantees",
            "Design patterns for synchronisation",
            "Concurrent objects",
            "Linearisability",
            "Transactional memory",
            "Actor model",
            "Message passing concurrency",
        ],
        "source": "imperial",
    },
]


def main():
    # Remove MIT OCW fallback directory
    if MIT_FALLBACK.exists():
        shutil.rmtree(MIT_FALLBACK)
        print(f"Removed {MIT_FALLBACK}")

    # Remove any remaining MIT JSON files directly in modules/
    for f in RAW_MODULES.glob("MIT*.json"):
        f.unlink()
        print(f"Removed {f}")

    # Create Imperial modules directory
    IMPERIAL_DIR.mkdir(parents=True, exist_ok=True)

    # Write each module JSON
    for module in MODULES:
        code = module["code"]
        path = IMPERIAL_DIR / f"{code}.json"
        with open(path, "w") as f:
            json.dump(module, f, indent=2)
        print(f"Written {path.name}")

    print(f"\nCreated {len(MODULES)} Imperial module files in {IMPERIAL_DIR}")


if __name__ == "__main__":
    main()

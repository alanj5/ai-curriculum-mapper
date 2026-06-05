#!/usr/bin/env python3
"""Create Imperial College Computing Department module JSON files.

Data sourced from the official course descriptor pages
  https://www.imperial.ac.uk/computing/current-students/courses/<CODE>/
for the BEng/MEng Computing programme (academic year 26-27), enumerated from
  https://www.imperial.ac.uk/computing/prospective-students/ug/beng-meng-computing/beng-comp/
(accessed June 2026). Descriptions, learning outcomes and syllabus topics are
taken from those pages. One module (60036 Compilers) has no live descriptor
page; its entry is supplemented from a standard public compilers curriculum and
flagged accordingly in its ``source`` field.

This covers the content modules of Years 1-3. Non-content entries are excluded:
extracurricular (COMPM0193/0701/0804), I-Explore / external placeholders
(COMPM035x), pure projects (60010 Individual Project, 60021 Group Project),
the teaching-placement module (60003), MATH-department finance electives, and
sub-part/lab variants (40018A, 50007.x, 50010.2).

Level convention:
  40xxx -> level 1 (Year 1)
  50xxx -> level 2 (Year 2)
  60xxx -> level 3 (Year 3)

Prerequisites encode the standard pedagogical knowledge dependencies of the
curriculum (the descriptor pages do not list formal prerequisites); they are
deliberately conservative and limited to unambiguous foundational links.
"""

import json
import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent
RAW_MODULES = BASE / "data" / "raw" / "modules"
MIT_FALLBACK = RAW_MODULES / "MIT_OCW_fallback"
IMPERIAL_DIR = RAW_MODULES / "imperial"

CREDITS = 8  # ECTS, uniform (descriptor pages vary 5-7.5; kept uniform as in v1)

MODULES = [
    # ── Year 1 (Level 1) ──────────────────────────────────────────────────
    {
        "code": "IC40001",
        "title": "Introduction to Computer Systems",
        "level": 1,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Study the fundamental principles and devices used in the design of "
            "digital computers, and the way in which primitive control logic can "
            "be organised to construct a programmable machine."
        ),
        "learning_objectives": [
            "Explain combinatorial circuit design and synchronous sequential circuit design",
            "Design a CPU using Boolean algebra and functional design",
            "Describe the basic architecture of a CPU and its components and explain how to map CPU control to hardware",
            "Compare and be able to use different number representations",
        ],
        "topics": [
            "Number representations and computer arithmetic",
            "Boolean algebra",
            "Combinatorial logic functions",
            "Principles of semiconductor devices and logic gates",
            "Adders, subtractors and multipliers",
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
        "credits": CREDITS,
        "prerequisites": ["IC40001"],
        "description": (
            "Develop a fundamental understanding of the organisation and operation "
            "of a computer system, from machine instructions to memory hierarchy "
            "and performance."
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
            "CISC and RISC instruction set architecture",
            "Assembler programming",
            "Memory organisation and spatial and temporal locality",
            "Performance estimation and Amdahl's Law",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40007",
        "title": "Introduction to Databases",
        "level": 1,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Learn how modern database systems are structured: model relational "
            "databases, normalise relational schemas, write SQL queries, and "
            "explore recent developments in database technology."
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
            "Views, integrity and security",
            "Transaction management and concurrency",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40008",
        "title": "Graphs and Algorithms",
        "level": 1,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Prove mathematical properties of graphs, explore classical algorithms "
            "for graphs and trees, design algorithms for sorting and searching, "
            "analyse time complexity, and study the complexity classes P and NP and "
            "NP-completeness."
        ),
        "learning_objectives": [
            "Prove basic properties of graphs",
            "Describe, and establish the correctness of, some of the fundamental algorithms in computing",
            "Analyse the time complexity of an algorithm",
            "Explain the complexity classes P and NP and the P=NP problem",
            "Determine to which complexity class a computational problem belongs",
        ],
        "topics": [
            "Graphs and graph representations",
            "Algorithms for graph traversal",
            "Minimum spanning trees",
            "Shortest paths",
            "Dynamic programming",
            "Divide and conquer",
            "Searching and sorting",
            "Algorithm analysis, recurrence relations and the Master Theorem",
            "Decision trees",
            "The complexity classes P and NP, NP-completeness",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40009",
        "title": "Computing Practical 1",
        "level": 1,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Develop practical skills including programming across major paradigms, "
            "web development, basic academic research, and written and oral "
            "communication, as important attributes of a professional software engineer."
        ),
        "learning_objectives": [
            "Demonstrate proficiency in using programming languages from three of the major paradigms",
            "Develop working solutions to well-specified programming problems of small to medium size",
            "Create a website that meets stakeholder needs",
            "Use core software development tools effectively, including those for version control",
            "Undertake basic research into Computing topics, including Computing ethics",
            "Write short technical documentation demonstrating proficiency in scientific communication",
            "Deliver short oral presentations summarising practical project work and research findings",
            "Operate effectively as a member of a group to produce deliverables",
        ],
        "topics": [
            "Functional programming in Haskell",
            "Functional and procedural programming in Kotlin",
            "Object-oriented programming in Kotlin and Java",
            "Assembler programming",
            "Programming in C",
            "Web development using HTML, CSS and JavaScript",
            "Computer systems project",
            "Introduction to research methods",
            "Introduction to ethics in Computing",
            "Introduction to academic writing",
            "Oral presentation skills",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40016",
        "title": "Calculus",
        "level": 1,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Study the calculus needed for many applications of Computing such as "
            "graphics, vision, robotics, operations research and statistical machine "
            "learning."
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
            "Limits of functions and continuity, intermediate value theorem",
            "Differentiation and its properties",
            "Mean value theorem",
            "Riemann integral and its properties",
            "Trapezium rule",
            "Uniform convergence and power series",
            "Metric spaces",
            "Contraction mapping theorem",
            "Multivariate differential calculus",
            "Partial derivatives",
            "Hessian and the Taylor series formula",
            "Extrema of scalar fields",
            "Newton's method",
            "Vector valued functions and the Jacobian matrix",
            "Cylindrical and spherical coordinate systems",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40017",
        "title": "Linear Algebra",
        "level": 1,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Study linear algebra, which underpins many applications of Computing "
            "involving analysis of aggregated data in vector or matrix form."
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
            "Rank and nullity theorem",
            "Scalar products",
            "Orthogonal subspaces",
            "Introduction to linear regression",
            "Eigenvalue and eigenvector problem",
            "Determinants and their properties",
            "Diagonalisability of matrices",
            "Cayley-Hamilton theorem",
            "Projections",
            "Rotation matrices",
            "Symmetric matrices and spectral decomposition",
        ],
        "source": "imperial",
    },
    {
        "code": "IC40018",
        "title": "Discrete Mathematics, Logic and Reasoning",
        "level": 1,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Learn how discrete mathematics and logic can be used to describe and "
            "reason about computational structures and systems, providing a foundation "
            "for hardware design, algorithm analysis and program reasoning, with an "
            "emphasis on proof techniques."
        ),
        "learning_objectives": [
            "Construct various types of mathematical proof using informal and formal reasoning",
            "Define properties of fundamental discrete structures such as sets, relations and functions",
            "Read, parse and evaluate logical formulas",
            "Formalise English statements into logic",
            "Use logic to specify the desired properties of a system, program or algorithm",
            "Use induction to reason about the correctness of recursive programs and data structures",
            "Provide suitable pre-, post- and mid-conditions and invariants for imperative program fragments",
            "Use logic to reason about the correctness of imperative programs",
        ],
        "topics": [
            "Logical connectives",
            "Proof methods",
            "Sets, relations and functions",
            "Countability",
            "Orderings",
            "Induction",
            "Inductive reasoning applied to recursive programs and data types",
            "Formalisation of logic syntax and semantics",
            "Validity and satisfiability",
            "Logical equivalence",
            "Logical proof systems, soundness and completeness",
            "Specification of pre-, post- and mid-conditions",
            "Loop invariants and variants",
            "Logical reasoning applied to imperative programs",
        ],
        "source": "imperial",
    },
    # ── Year 2 (Level 2) ──────────────────────────────────────────────────
    {
        "code": "IC50001",
        "title": "Algorithm Design and Analysis",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC40008"],
        "description": (
            "Explore the main algorithmic design paradigms, apply algorithmic "
            "techniques to practical and unseen problems, quantitatively analyse "
            "the performance of algorithms, and model the mathematical structure of "
            "computational tasks."
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
            "Divide and conquer",
            "Dynamic programming",
            "Greedy algorithms",
            "Randomised algorithms",
            "Advanced graph algorithms",
            "String processing algorithms",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50002",
        "title": "Software Engineering Design",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Examine the effects of design choices on flexibility, maintainability "
            "and cost; practise refactoring and automated testing; select appropriate "
            "design patterns; and reflect on technical practices within iterative "
            "delivery."
        ),
        "learning_objectives": [
            "Identify and describe various design patterns, the problems they address, and trade-offs involved",
            "Make informed engineering decisions to minimise the cost of change",
            "Implement common design structures for various common software application types",
            "Construct automated tests for code through test-driven development",
            "Perform refactoring operations on a codebase using appropriate tools",
            "Consider and critique the qualities of the design of a given codebase",
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
        ],
        "source": "imperial",
    },
    {
        "code": "IC50003",
        "title": "Models of Computation",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC40018"],
        "description": (
            "Formal descriptions (models) of computational behaviour, covering "
            "operational semantics, programming language styles, and foundational "
            "definitions of algorithm and computable function."
        ),
        "learning_objectives": [
            "Provide formal descriptions of the precise behaviour of several styles of programming language",
            "Prove properties of such languages",
            "Provide several formal definitions of algorithm",
            "Link the definition of algorithm with the fundamental notion of a computable function",
        ],
        "topics": [
            "Operational semantics for a simple while language and extensions",
            "Properties of programming languages such as confluence and totality",
            "Inductive proofs for WHILE and extensions",
            "Register machines and the universal register machine",
            "Computable functions expressed as register machines",
            "The halting problem for register machines",
            "Turing machines",
            "The lambda calculus and language properties",
            "The Church-Turing thesis",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50004",
        "title": "Operating Systems",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC40005"],
        "description": (
            "Develop an understanding of the main operating system abstractions, "
            "explore trade-offs in their implementation, and investigate mechanisms "
            "for resource management in modern operating systems."
        ),
        "learning_objectives": [
            "Distinguish between different styles of operating system design",
            "Explain the main principles behind resource abstraction and resource management",
            "Explain the main principles behind process isolation and process and thread models",
            "Explain scheduling and the mechanisms behind inter-process communication",
            "Identify the main problems related to concurrency and explain synchronisation mechanisms",
            "Evaluate security risks in operating systems and the role operating systems play in security",
        ],
        "topics": [
            "Operating system kernel organisation",
            "Process and thread abstractions",
            "Inter-process synchronisation mechanisms",
            "Concurrency control and scheduling algorithms",
            "Virtual memory abstractions and on-demand paging",
            "Device and disk management",
            "I/O APIs and file system abstractions",
            "Basic security concepts and attacks",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50005",
        "title": "Networks and Communications",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": [],
        "description": (
            "Study the principles of computer networking, analyse the OSI and TCP/IP "
            "models, design a network from requirements, and become familiar with the "
            "basic principles of computer security."
        ),
        "learning_objectives": [
            "Define and classify the major concepts of computer networking",
            "Design a computer network based on given requirements",
            "Calculate important network metrics",
            "Identify and analyse potential security risks",
        ],
        "topics": [
            "Introduction to networking concepts",
            "The application, presentation and session layers",
            "The transport layer",
            "Network security",
            "The network layer",
            "The data link layer",
            "The physical layer",
            "Client/server programming",
            "Future directions",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50008",
        "title": "Probability and Statistics",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC40016"],
        "description": (
            "Use probability theory to model uncertainty, design simple probabilistic "
            "models that facilitate prediction, conduct sound scientific analysis of "
            "data, and study the foundations of probabilistic modelling with Markov "
            "chains and simulation."
        ),
        "learning_objectives": [
            "Describe notions of probability in terms of sample spaces",
            "Define and use random variables",
            "Design simple probability models and estimate their parameters from data",
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
        ],
        "source": "imperial",
    },
    {
        "code": "IC50009",
        "title": "Symbolic Reasoning",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC40018"],
        "description": (
            "The foundations of symbolic reasoning: SAT solving, logic programming, "
            "answer set programming and SMT solving, with the practical skills to "
            "solve real-world problems in program reasoning and symbolic artificial "
            "intelligence."
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
            "Boolean satisfiability and NP-completeness",
            "DP and DPLL algorithms",
            "Conflict-driven clause learning",
            "Knowledge representation and reasoning",
            "Logic programming syntax and semantics",
            "Herbrand models and stable models",
            "SLD and SLDNF resolution",
            "Answer set programming",
            "First-order theories and decidability",
            "Lazy SMT solving and the DPLL(T) architecture",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50010",
        "title": "Designing for Real People",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC50002"],
        "description": (
            "Apply software engineering techniques to implement a large web-based or "
            "mobile application that solves a real-world problem, following "
            "human-centred design and agile development."
        ),
        "learning_objectives": [
            "Describe and discuss the concepts involved in Human-Centred Design and agile software development",
            "Conduct research into a real-world problem following HCD principles",
            "Design, engineer and deploy a web-based or mobile-based application to solve a real-world problem",
            "Work effectively as part of a small group to deliver software iteratively using agile methods",
            "Report, present and demonstrate a solution and its value proposition to an interdisciplinary audience",
            "Recall relevant Computer Laws and act in conformity with those laws",
        ],
        "topics": [
            "Human-centred design",
            "Agile software development",
            "Design and implementation of a multi-user application",
            "Copyright and data protection law",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50011",
        "title": "Computational Techniques",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC40017", "IC40016"],
        "description": (
            "Additional mathematical topics that form prerequisites for later "
            "modules in computer graphics, machine learning and computational "
            "finance, focusing on how mathematical methods apply to complex "
            "computational problems."
        ),
        "learning_objectives": [
            "Apply advanced topics in linear algebra to problems in machine learning and deep learning",
            "Understand and implement mathematical methods in image processing, graphics and computational finance",
            "Use vector calculus to solve computational optimisation problems",
        ],
        "topics": [
            "Vector and matrix norms",
            "Generalised eigenvectors and Jordan normal form",
            "Singular value decomposition",
            "Dimensionality reduction",
            "Positive definite matrices and Cholesky factorisation",
            "Normal equations and the least squares method",
            "QR decomposition and Householder transform",
            "LU decomposition",
            "Condition of a matrix and stability of algorithms",
            "Iterative solution of linear systems (Jacobi, Gauss-Seidel)",
            "Iterative computation of eigenvectors (power method, inverse iteration, Rayleigh quotient)",
            "Steepest descent and conjugate gradient methods",
            "Linear programming",
        ],
        "source": "imperial",
    },
    {
        "code": "IC50013",
        "title": "Machine Learning",
        "level": 2,
        "credits": CREDITS,
        "prerequisites": ["IC50008", "IC40017"],
        "description": (
            "Foundational and advanced machine learning concepts, including supervised "
            "and unsupervised learning, neural networks, model evaluation, and "
            "evolutionary algorithms."
        ),
        "learning_objectives": [
            "Explain the strengths and weaknesses of machine learning algorithms",
            "Appraise the suitability of a machine learning algorithm to solve a given problem",
            "Provide appropriate methodologies to evaluate machine learning algorithms",
            "Implement algorithms to solve machine learning problems",
            "Develop predictive models with machine learning algorithms",
            "Apply unsupervised clustering programs based on machine learning algorithms",
        ],
        "topics": [
            "Machine learning concepts, taxonomies and the supervised learning pipeline",
            "Feature encoding and the bias-variance tradeoff",
            "Instance-based learning: k-nearest neighbours, locally weighted regression",
            "Decision trees",
            "Model evaluation, cross-validation and statistical significance",
            "Neural networks: perceptron, multilayer perceptron, back-propagation",
            "Stochastic gradient descent, activation functions and overfitting",
            "Unsupervised learning: k-means clustering",
            "Density estimation: kernel density, Gaussian and Gaussian mixture models",
            "Evolutionary algorithms: genetic algorithms and evolutionary strategies",
        ],
        "source": "imperial",
    },
    # ── Year 3 (Level 3) ──────────────────────────────────────────────────
    {
        "code": "IC60001",
        "title": "Advanced Computer Architecture",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC40005"],
        "description": (
            "The design of general-purpose and special-purpose processors and parallel "
            "computer systems, covering high-performance and energy-efficient "
            "architecture and current trends in processor design."
        ),
        "learning_objectives": [
            "Justify the design of leading-edge processor products from microarchitecture to large-scale parallel systems",
            "Evaluate architecture design alternatives and tradeoffs in terms of power and performance",
            "Identify architectural security hazards and attack vulnerabilities and explain how they can be mitigated",
            "Optimise application software kernels to exploit architectural capabilities effectively",
        ],
        "topics": [
            "Pipelines, hazards and instruction-level parallelism",
            "Locality and caching",
            "Dynamic scheduling, Tomasulo's algorithm and register renaming",
            "Software instruction scheduling and software pipelining",
            "Superscalar and long-instruction-word architectures",
            "Branch prediction and speculative execution",
            "Simultaneous multithreading",
            "Vector instruction execution",
            "Cache coherency, memory systems and address translation",
            "Graphics processors and manycore architectures",
            "Security vulnerabilities and their mitigation",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60005",
        "title": "Graphics",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC40017", "IC40016"],
        "description": (
            "Core computer graphics concepts, including the mathematical principles "
            "used for computer generated imagery, shading and light approximations."
        ),
        "learning_objectives": [
            "Explain the core principles of programmable shading pipelines such as vertex, fragment and geometry shading",
            "Compare and contrast methods for modelling object geometry and surfaces",
            "Describe polyhedral and ray-based rendering methods and evaluate their tradeoffs",
            "Analyse and deploy fundamental algorithms associated with computer graphics",
            "Read, explain and adapt existing graphics source code and computer graphics pipeline diagrams",
            "Design, analyse and implement new software for solving complex computer graphics problems",
        ],
        "topics": [
            "Device-independent graphics",
            "Polygon rendering",
            "3D geometry",
            "Texture mapping and anti-aliasing",
            "Shading planar polygons",
            "Representation of colours",
            "Ray tracing",
            "Radiosity",
            "Geometric warping and morphing",
            "Special visual effects and particle systems",
            "Inverse kinematics in animation",
            "Non-photorealistic rendering",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60006",
        "title": "Computer Vision",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC40017", "IC50013"],
        "description": (
            "How images are represented on computers and how they can be analysed by "
            "computer algorithms to extract semantic information."
        ),
        "learning_objectives": [
            "Differentiate commonly used filters for image processing, edge detection and interest point detection",
            "Describe features and classifiers used for image classification",
            "Implement neural networks for image classification",
            "Extend image classification methods to object detection and image segmentation",
            "Recall commonly used methods for motion estimation and object tracking",
            "Transform between the 2D coordinate system of an image and the 3D world",
        ],
        "topics": [
            "Image filtering",
            "Edge detection and interest point detection",
            "Feature descriptors",
            "Image classification",
            "Object detection and image segmentation",
            "Neural networks",
            "Motion estimation",
            "3D vision",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60007",
        "title": "The Theory and Practice of Concurrent Programming",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50004"],
        "description": (
            "Modern concurrent programming models and the challenges of writing correct "
            "concurrent code, covering shared memory concurrency from architectural "
            "foundations to high-level synchronisation, with a focus on correctness "
            "through formal specification and verification."
        ),
        "learning_objectives": [
            "Write correct and efficient concurrent software in modern programming languages",
            "Evaluate the strengths and weaknesses of a variety of concurrency models",
            "Explain the architectural mechanisms for supporting shared memory concurrency",
            "Formalise the semantics of shared memory concurrency",
            "Specify, test and verify properties of concurrent systems using practical tools and formal methods",
        ],
        "topics": [
            "Shared memory concurrent programming in C++",
            "Synchronisation using locks and atomic operations",
            "Implementation of synchronisation primitives",
            "Functional programming and concurrency",
            "Dynamic data race detection",
            "Architecture support for single- and multi-core shared memory",
            "Strong and weak memory models",
            "Races, deadlocks, livelocks and progress guarantees",
            "Design patterns for synchronisation: mutexes, locks, monitors",
            "Concurrent objects and linearisability",
            "Transactional memory",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60008",
        "title": "Custom Computing",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC40005"],
        "description": (
            "Applications of custom computing designs in areas such as signal "
            "processing and genomics data analysis, and the development of parametric "
            "descriptions for custom computing designs."
        ),
        "learning_objectives": [
            "Develop parametric descriptions of custom computing designs",
            "Develop alternatives for custom computing designs that meet specified requirements",
            "Analyse the performance of a custom computing design in terms of time and space",
            "Evaluate space/time trade-offs between competing custom computing designs to determine optimal solutions",
            "Use simulation to compare the intended and actual behaviour of custom computing designs",
        ],
        "topics": [
            "Special-purpose computer systems customised for specific applications",
            "Signal processing applications",
            "Genomics data analysis applications",
            "Techniques for describing custom computing designs",
            "Evaluating custom computing designs",
            "Optimisation methods for throughput and energy efficiency",
            "Design tools to simulate design behaviour",
            "Space and time trade-offs",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60013",
        "title": "Logic-Based Learning",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50009"],
        "description": (
            "Foundation knowledge and principles of logic-based machine learning, "
            "covering semantics, current learning algorithms and heuristics, and "
            "skills for formalising logic-based learning tasks for real-world problems."
        ),
        "learning_objectives": [
            "Explain the semantic foundations and differences of logic-based machine learning problems",
            "Formalise a learning task as a logic-based learning task",
            "Apply algorithms to solve learning tasks in different semantic contexts",
            "Use Answer Set Programming to solve real-world problems",
            "Apply algorithms for learning Answer Set programs",
            "Evaluate current forms of probabilistic logic-based inference and learning",
            "Explain and apply state-of-the-art algorithms for probabilistic learning",
        ],
        "topics": [
            "Deductive, abductive and inductive reasoning",
            "Bayesian reasoning techniques",
            "Answer set programming",
            "Top-down and bottom-up approaches to learning",
            "Meta-level logic-based learning",
            "Monotonic and non-monotonic learning",
            "Enhanced logic programming systems",
            "Soundness and completeness of learning algorithms",
            "Probabilistic inductive learning",
            "Probabilistic logic programming",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60015",
        "title": "Network and Web Security",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50005"],
        "description": (
            "A broad knowledge of network and web security from the network to the "
            "application layer, emphasising both underlying principles and techniques "
            "and how they are applied in practice."
        ),
        "learning_objectives": [
            "Evaluate main threats, attack techniques and defences relevant to cybersecurity and network security",
            "Analyse web applications in order to identify vulnerabilities",
            "Propose countermeasures to address vulnerabilities",
            "Design secure web applications by leveraging security principles",
        ],
        "topics": [
            "Cybersecurity overview",
            "Threat analysis and bug finding",
            "Internet security",
            "Server-side security",
            "Client-side security",
            "Secure web sessions",
            "Emerging security standards",
            "Online privacy issues",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60016",
        "title": "Operations Research",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC40017"],
        "description": (
            "Quantitative mathematical methods for taking decisions in the presence of "
            "constraints or finite resources, covering linear programming, integer "
            "linear programming, robust optimisation and game theory."
        ),
        "learning_objectives": [
            "Classify mathematical programs on the basis of the number and types of their solutions",
            "Apply linear programming to real-world decision problems with real and integer-valued variables",
            "Model adversarial decision problems using linear programming",
            "Select an appropriate solution method or synthesise a new method for a given mathematical program",
            "Formulate mathematical programs for decision-making and decision-making under uncertainty",
            "Formulate an adversarial decision problem in terms of a game",
        ],
        "topics": [
            "Introduction to linear programming",
            "Basic feasible solutions",
            "Simplex method",
            "Degenerate linear programs",
            "Duality and shadow prices",
            "Integer linear programming",
            "Cutting planes",
            "Branch-and-bound and branch-and-cut",
            "Game theory and robust optimisation",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60017",
        "title": "System Performance Engineering",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50004"],
        "description": (
            "Ensuring that computer systems, comprising hardware and software, are "
            "responsive, scalable and efficient, teaching the design of performance "
            "assessments, resource provisioning, bottleneck resolution and balancing "
            "of resource utilisation."
        ),
        "learning_objectives": [
            "Explain and apply the design principles, techniques, tools and metrics of performance assessment",
            "Make and explain performance trade-offs in software and hardware systems",
            "Forecast performance of a system or application with the aim to improve it",
            "Apply the principles, techniques and tools of performance optimisation",
        ],
        "topics": [
            "Performance engineering methodology",
            "Profiling systems to find bottlenecks",
            "Macro and micro-benchmarking",
            "Critical sections",
            "Cost modeling",
            "Resource management",
            "Scaling up and out",
            "Single-thread, multi-thread and multi-process performance",
            "Performance-critical operating system features",
            "Specialised devices",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60019",
        "title": "Robotics",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50008"],
        "description": (
            "Mobile robotics, emphasising practical algorithms for navigation based on "
            "real hardware and tested in the real world, including localisation, "
            "mapping, planning and an introduction to SLAM."
        ),
        "learning_objectives": [
            "Build, program and experiment with practical robots",
            "Calibrate and model imperfect motors and sensors",
            "Use knowledge of feedback control to implement sensor/motor control loops",
            "Use probabilistic methods to implement 2D localisation and mapping on a mobile robot",
            "Evaluate algorithms for relocalisation, mapping and planning in mobile robot navigation systems",
        ],
        "topics": [
            "Mobile robotics and the state of the art",
            "Robot motion: wheel kinematics, motors, gearing, PID control",
            "Motion uncertainty",
            "Sensors, processing and control loops with feedback",
            "Reactive behaviours",
            "Probabilistic methods in robotics",
            "Monte Carlo localisation",
            "Place recognition, occupancy mapping and dynamic window planning",
            "Simultaneous localisation and mapping (SLAM)",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60023",
        "title": "Type Systems for Programming Languages",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50003"],
        "description": (
            "The design of type assignment systems for programming languages, focusing "
            "on a sound theoretical framework for reasoning about typed programs, and "
            "comparing the type systems of modern functional and object-oriented "
            "languages."
        ),
        "learning_objectives": [
            "Evaluate the relative merits of dynamic and static typing for functional, imperative and object-oriented languages",
            "Formalise type systems and prove properties such as decidability, soundness and completeness",
            "Describe and implement algorithms for type inference and type checking",
            "Describe and formalise type system extensions required to support modern programming language features",
            "Demonstrate advanced features of modern statically-typed programming languages through small applications",
        ],
        "topics": [
            "Lambda calculus",
            "Curry type assignment and principal types",
            "Recursion and polymorphism",
            "Type checking versus type inference",
            "System F",
            "Extensions for practical type inference: data types, type classes, type constraints",
            "Subtypes and subtype inference",
            "Higher-rank types",
            "Dependent types and ownership types",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60032",
        "title": "Networked Systems",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50005"],
        "description": (
            "An overview of and hands-on experience with how modern networked systems "
            "are designed and implemented, across control plane, data plane and "
            "endpoints."
        ),
        "learning_objectives": [
            "Enumerate and analyse basic network mechanisms, their design and implementation across different settings",
            "Design and reason about scalability and performance requirements for parts of the networking infrastructure",
            "Use network simulation, debugging and monitoring tools such as wireshark, tcpdump and NS2",
            "Implement a network middlebox in different technologies such as eBPF, DPDK and P4",
        ],
        "topics": [
            "TCP/IP stack, remote procedure calls and network stack design",
            "Network architecture and topologies: WAN, datacenter networks, optical networking",
            "Switch architecture",
            "Control plane: routing algorithms BGP and OSPF",
            "Software-defined networks",
            "Programmable dataplanes: P4, match-action tables",
            "Queueing theory, packet scheduling and quality of service",
            "Congestion control and flow control",
            "Kernel-bypassing, eBPF and virtual networking",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60034",
        "title": "Deep Learning",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50013"],
        "description": (
            "The fundamental concepts and advanced methodologies of deep learning and "
            "their relation to real-world problems in a variety of domains."
        ),
        "learning_objectives": [
            "Express and relate the underlying theoretical concepts of modern deep learning methods",
            "Compare, characterise and quantitatively evaluate various deep learning approaches",
            "Evaluate the limitations of deep learning",
            "Apply deep learning techniques to real-world problems in computer vision, speech, text analysis and graph processing",
        ],
        "topics": [
            "Supervised versus unsupervised learning, generalisation and overfitting",
            "Perceptrons and deep versus shallow models",
            "Stochastic gradient descent and backpropagation",
            "Convolutional neural networks and applications in image analysis",
            "Recurrent neural networks, LSTM and gated recurrent units",
            "Applications of RNNs in speech analysis and machine translation",
            "Variational autoencoders",
            "Generative adversarial networks and image generation",
            "Graph neural networks: spectral and spatial methods, message passing",
            "Applications of graph neural networks",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60035",
        "title": "Natural Language Processing",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50013"],
        "description": (
            "The foundations, building blocks and applications of Natural Language "
            "Processing, with an emphasis on approaches based on deep learning, "
            "covering word representations, classification and tagging tasks, sequence "
            "models and machine translation."
        ),
        "learning_objectives": [
            "Describe and critically appraise NLP approaches used to support deep learning activities",
            "Model words and languages using appropriate NLP representations",
            "Discuss approaches to classification tasks such as sentiment analysis and tagging tasks such as part-of-speech tagging",
            "Apply state-of-the-art tools and techniques to solve real-world NLP problems",
        ],
        "topics": [
            "Introduction to NLP",
            "Word meaning and representations",
            "Classification tasks: spam detection, sentiment analysis",
            "Language models: n-gram, RNN and GPT",
            "Part-of-speech tagging",
            "Parsing",
            "Sequence to sequence models",
            "Machine translation",
        ],
        "source": "imperial",
    },
    {
        "code": "IC60036",
        "title": "Compilers",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC50003"],
        "description": (
            "The theory and practice of compiler construction: how a high-level "
            "programming language is translated into executable code, covering the "
            "standard compiler pipeline from lexical analysis through parsing, semantic "
            "analysis, intermediate representation, optimisation and code generation."
        ),
        "learning_objectives": [
            "Describe the phases of a modern compiler and how they interact",
            "Implement lexical analysis and parsing for a programming language",
            "Perform semantic analysis and type checking using symbol tables",
            "Generate and optimise intermediate representations of programs",
            "Generate target machine code and perform register allocation",
        ],
        "topics": [
            "Lexical analysis",
            "Regular expressions and finite automata",
            "Context-free grammars",
            "Top-down and bottom-up parsing (LL and LR)",
            "Abstract syntax trees",
            "Semantic analysis and symbol tables",
            "Type checking",
            "Intermediate representations",
            "Data-flow analysis",
            "Compiler optimisation",
            "Code generation",
            "Register allocation",
            "Runtime systems",
        ],
        "source": "imperial (descriptor page unavailable; syllabus from standard public compilers curriculum)",
    },
    {
        "code": "IC60037",
        "title": "Mathematics for Machine Learning",
        "level": 3,
        "credits": CREDITS,
        "prerequisites": ["IC40016", "IC40017"],
        "description": (
            "Advanced mathematical techniques required to understand, design and "
            "implement modern statistical machine learning algorithms and inference "
            "mechanisms."
        ),
        "learning_objectives": [
            "Implement foundational machine learning algorithms from scratch",
            "Apply appropriate mathematical techniques in a machine learning setting",
            "Critically assess the quality of machine learning models",
            "Evaluate connections between different machine learning algorithms",
        ],
        "topics": [
            "Multivariate calculus",
            "Multivariate probability: joint distributions, means and covariance matrices",
            "Conditional probability and Bayes's rule",
            "Maximum likelihood estimation",
            "Monte Carlo estimation",
            "Validation, test error estimation and cross-validation",
            "Concentration inequalities and the law of large numbers",
            "Gradient descent and its convergence",
            "Principal component analysis, eigendecomposition and SVD",
            "Bayesian inference and MAP inference",
            "Multivariate Gaussians",
            "Bayesian linear regression",
        ],
        "source": "imperial",
    },
]


def main():
    # Remove MIT OCW fallback directory and any stray MIT JSONs
    if MIT_FALLBACK.exists():
        shutil.rmtree(MIT_FALLBACK)
        print(f"Removed {MIT_FALLBACK}")
    for f in RAW_MODULES.glob("MIT*.json"):
        f.unlink()
        print(f"Removed {f}")

    # Rebuild the Imperial modules directory from scratch so stale modules
    # (e.g. renamed/removed codes) do not linger from a previous run.
    if IMPERIAL_DIR.exists():
        shutil.rmtree(IMPERIAL_DIR)
    IMPERIAL_DIR.mkdir(parents=True, exist_ok=True)

    codes = [m["code"] for m in MODULES]
    assert len(codes) == len(set(codes)), "Duplicate module codes detected"

    for module in MODULES:
        path = IMPERIAL_DIR / f"{module['code']}.json"
        with open(path, "w") as f:
            json.dump(module, f, indent=2)
        print(f"Written {path.name}")

    by_level = {}
    for m in MODULES:
        by_level[m["level"]] = by_level.get(m["level"], 0) + 1
    print(f"\nCreated {len(MODULES)} Imperial module files in {IMPERIAL_DIR}")
    print(f"By level: {dict(sorted(by_level.items()))}")


if __name__ == "__main__":
    main()

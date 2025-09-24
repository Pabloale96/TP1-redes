\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{style}
\LoadClass[10pt]{article}

\RequirePackage{hyperref}
\RequirePackage{verbatim}
\RequirePackage{attachfile2}
\RequirePackage{etoolbox}
\RequirePackage{xparse}
\RequirePackage{pgffor}
\RequirePackage{arrayjobx}
\RequirePackage{graphicx}
\RequirePackage{fancyhdr}
\RequirePackage{lastpage}
\RequirePackage[document]{ragged2e}
\RequirePackage{lipsum}
\RequirePackage{translations}
\RequirePackage{ifthen}
\RequirePackage{xstring}
\RequirePackage[a4paper, left=30mm, right=30mm, top=30mm, bottom=30mm, marginpar=25mm]{geometry}
\RequirePackage{csquotes}


\RequirePackage{tikz}

\RequirePackage{xfp}

% Función para poner los asteriscos
\newcommand{\andreas}[5][1.0]{
    \begin{scope}[shift={(#2,#3)},rotate=45,scale=#4,transparency group,opacity=#1]
        \fill[fill=#5] (0,0) -- (0,1) -- (3,1) -- (3,0);
        \fill[fill=#5] (1,-1) -- (2,-1) -- (2,2) -- (1,2);
    \end{scope}
}

\newcommand{\andreasline}{
    \centering\begin{tikzpicture}
        \newcommand\numcross{29}
        \foreach \n in {1,...,\the\numexpr\numcross\relax} {
            \andreas[\fpeval{0.9*sin((\n + 1)*pi/(\numcross+2))}]{0.5*\n}{0}{0.10}{black}
        }
    \end{tikzpicture}
}

\newcommand{\andreaslineslim}{
    \centering\begin{tikzpicture}[baseline]
        \newcommand\numcross{74}
        \foreach \n in {1,...,\the\numexpr\numcross\relax} {
            \andreas[0.75]{0.2*\n}{0}{0.04}{black}
        }
    \end{tikzpicture}
}


\newcommand{\MemberLeft}[2]{%
  \begin{minipage}[t]{0.48\textwidth}\raggedright
    \large #1\\ \normalsize #2
  \end{minipage}%
}
\newcommand{\MemberRight}[2]{%
  \begin{minipage}[t]{0.48\textwidth}\raggedleft
    \large #1\\ \normalsize #2
  \end{minipage}%
}
\newcommand{\MemberRow}[4]{%
  \noindent\makebox[\textwidth][c]{%
    \MemberLeft{#1}{#2}\hfill \MemberRight{#3}{#4}%
  }\par\vspace{0.5\baselineskip}%
}
\newcommand{\MemberSingleCentered}[2]{%
  \noindent\makebox[\textwidth][c]{%
    \begin{minipage}[t]{0.48\textwidth}\centering
      \large #1\\ \normalsize #2
    \end{minipage}}%
  \par\vspace{0.5\baselineskip}%
}
%------------------------------------------------------------------------------
%	HEADERS, FOOTERS EN SECCIONES
%------------------------------------------------------------------------------
\pagestyle{fancy}
\setlength{\headheight}{27pt}

\renewcommand{\headrulewidth}{1pt}
\renewcommand{\footrulewidth}{1pt}
\rhead{\footnotesize \textsc {Trabajo Práctico 0\\ Redes}} % Trabajo práctico
\lhead{\includegraphics[width=2.5cm]{logo}}
\cfoot{\small \textsc {Página \thepage\ de \pageref*{LastPage}}}

\fancypagestyle{firststyle}
 {
  \fancyhf{}
   \renewcommand{\headrulewidth}{0pt}
 }




%------------------------------------------------------------------------------
%	CARÁTULA
%------------------------------------------------------------------------------

\renewcommand*{\maketitle}{
\thispagestyle{firststyle}
\begin{center}
\includegraphics[width=7cm]{logo}
\\[1cm]
	\textsc{\Large Redes}\\           % Materia
	\textsc{\small Curso Hamelin}\\[0.4cm]    % Subtítulo materia
	{ \huge \bfseries Trabajo Práctico 0 \\ Protocolo sobre TCP}\\[0.3cm]      % Título
	\andreasline \\[0.2cm]
	{\large \today  \\[0.4cm]}                          % Fecha
\MemberRow{Nervo Olalla}{111731}{Pablo Alejandro}{98021}
\MemberRow{Matias Gutierrez}{92172}{Noel Escobar}{111151}
\MemberSingleCentered{Tom Pinargote}{111689}

 \end{center}
}

import glob
import nbformat
import codecs
import sys
import subprocess


verbose = True


def create_question(notebook):

    if '_Solution' in notebook:
        out_notebook = notebook.split('_Solution')[0] + notebook.split('_Solution')[1]
    else:
        print(f'Warning: _Solution not found in notebook name {notebook}. Quitting...')
        out_notebook = ''
        exit(1)

    if verbose:
        print(f'Converting {notebook}...')

    nb = nbformat.read(notebook, nbformat.NO_CONVERT)

    # outputs = None
    solution = None
    cells_to_keep = []
    question_nr = 0
    reveal = 0
    section = 0
    subsection = 0
    for i in nb['cells']:
        source = i['source']
        # print(f'\n_______\nSTART\n_______\n{i}')
        if i['cell_type'] == 'code':
            if '# @manage_solutions' in source:
                if solution is not None:
                    cells_to_keep.append(solution)
                    solution = None
                # code = i['source']
                code = "# @info: Exécutez-moi pour activer les questions interactives\n" \
                       "# -----------------------------------------------------------\n\n" \
                       "from IPython.display import HTML\nimport codecs\n\n# @hidden\nHTML('''\n<script>\ncode_show=true;\nfunction code_toggle() {\n if (code_show){\n" \
                       "  $('.cm-comment:contains(@hidden)').closest('div.input').hide();\n } else {\n" \
                       "  $('.cm-comment:contains(@hidden)').closest('div.input').show();\n }\n code_show = !code_show\n}\n" \
                       "$( document ).ready(code_toggle);\n</script>\n" \
                       "<div># @info: Exécutez-moi pour activer les questions interactives </div>\n''')"
                i['source'] = code
                i['outputs'] = [nbformat.notebooknode.NotebookNode({'name': 'stdout', 'output_type': 'stream',
                                                                    'text': '# @info: Exécutez-moi pour cacher le code, puis sauvegardez le notebook\n'})]
                cells_to_keep.append(i)

            elif '# @solution' in source:
                if '@reveal' in source:
                    if solution is not None:
                        cells_to_keep.append(solution)
                        solution = None
                    code = source.replace('# @solution', '').replace('@reveal', '').replace('@keep_output', '').replace(
                        '\n', '<br>\n').lstrip()
                    while code.startswith('<br>\n'):
                        code = code[5:]

                    s = f"""<div class=\"alert alert-block alert-warning\">\n\tSi vous être bloqué(e),
                    affichez une solution en pressant sur le bouton ci-dessous.<br>\n\tVeillez à <b>comprendre</b> la solution
                    et à la tester par vous-même.\n</div> <br>\n\n<button data-toggle=\"collapse\" data-target=\"#reveal_{reveal:04d}">
                    Afficher le code</button>\n<div id="reveal_{reveal:04d}" class="collapse">\n<br><code>{code}\n</code>\n</div>\n
                    """
                    sx = codecs.encode(codecs.encode(s, 'utf8'), 'hex')
                    i['source'] = f"# @hidden\nsx={sx}\nHTML(codecs.decode(codecs.decode(sx,'hex'), 'utf8'))"
                    # i.pop('execution_count')
                    outputs = i.pop('outputs')
                    # i['cell_type'] = 'raw'
                    i['outputs'] = [nbformat.notebooknode.NotebookNode({'name': 'stdout', 'output_type': 'stream',
                                                                        'text': "# @info: Exécutez-moi pour accéder à l'aide interactive\n"})]
                    cells_to_keep.append(i)
                    reveal += 1
                    if '@keep_output' in source:
                        solution = nbformat.v4.new_code_cell(source='# Résultat attendu ci-dessous...', outputs=outputs)
                        solution.pop('id')
                        cells_to_keep.append(solution)
                        solution = None
                else:
                    i.source = ''
                    if '@keep_output' in source:
                        if solution is not None:
                            cells_to_keep.append(solution)
                            solution = None
                        solution = nbformat.v4.new_code_cell(source='# Résultat attendu ci-dessous...',
                                                             outputs=i['outputs'])
                        solution.pop('id')
                        cells_to_keep.append(solution)
                        solution = None
                    else:
                        i.outputs = []
                        solution = i
            else:
                if solution is not None:
                    solution['outputs'] = []
                    cells_to_keep.append(solution)
                    solution = None
                cells_to_keep.append(i)
        elif i['cell_type'] == 'markdown':
            if '## @question\n' in source:
                if solution is not None:
                    cells_to_keep.append(solution)
                solution = None
                qa = source.rsplit('## @answer\n')
                question = qa[0].strip('## @question\n')
                if len(qa)>1:
                    answer = qa[1]
                    s = f"""<div class="alert alert-block alert-warning">\n{question}\n</div> <br>\n<button data-toggle="collapse"
                    data-target="#question_{question_nr:04d}">Afficher la réponse</button>\n\n<div id="question_{question_nr:04d}"
                    class="collapse">{answer}\n</div>\n"""
                    sx = codecs.encode(codecs.encode(s, 'utf8'), 'hex')
                    i['source'] = f"# @hidden\nsx={sx}\nHTML(codecs.decode(codecs.decode(sx,'hex'), 'utf8'))"
                    i['cell_type'] = 'code'
                    i['execution_count'] = None
                    i['outputs'] = [nbformat.notebooknode.NotebookNode({'name': 'stdout', 'output_type': 'stream',
                                                                        'text': '# @info: Exécutez-moi pour afficher la question interactive\n'})]
                else:
                    s = f"""<div class="alert alert-block alert-warning">\n{question}\n</div>"""
                    i['source'] = s

                cells_to_keep.append(i)
                question_nr += 1
            elif '## @tip' in source:
                tip = source.replace('# @tip', '').replace('\n', '<br>\n').lstrip()
                while tip.startswith('<br>\n'):
                    tip = tip[5:]
                i['source'] = f'<div class="alert alert-block alert-info">\n<b>Tip:</b> {tip}\n</div>'
            elif "## @section" in source:
                section += 1
                if solution is not None:
                    cells_to_keep.append(solution)
                solution = None
                i['source'] = '***\n'
                title = source.split(' | ', 1)[1]
                i['source'] += f'## {section}. {title}'
                cells_to_keep.append(i)
                subsection = 0
            elif "## @subsection" in source:
                subsection += 1
                if solution is not None:
                    cells_to_keep.append(solution)
                solution = None
                logo_html = None
                if "@r_code" in source:
                    logo_html = '<img align="right" src="http://localhost:8888/kernelspecs/ir/logo-64x64.png" width="24"/>'
                elif "@python_code" in source:
                    logo_html = '<img align="right" src="http://localhost:8888/kernelspecs/python3/logo-64x64.png" width="24"/>'
                i['source'] = '<div class="alert alert-block alert-success">\n'
                if logo_html is not None:
                    i['source'] += '\t'
                    i['source'] += logo_html
                title = source.split(' | ', 1)[1]
                i['source'] += '\t'
                i['source'] += f'<b>{section}.{subsection} {title}</b>'
                i['source'] += '\n</div>'
                cells_to_keep.append(i)
            else:
                if solution is not None:
                    solution['outputs'] = []
                    cells_to_keep.append(solution)
                    solution = None
                cells_to_keep.append(i)
        else:
            if solution is not None:
                solution['outputs'] = []
                cells_to_keep.append(solution)
                solution = None
            cells_to_keep.append(i)

    if solution is not None:
        cells_to_keep.append(solution)
        # print(f'\n_______\nEND\n_______\n{cells_to_keep[-1]}')
    nb['cells'] = cells_to_keep

    nbformat.write(nb, out_notebook, version=nbformat.NO_CONVERT)
    return out_notebook


def remove_solutions(parent_dir='.'):
    to_remove = glob.glob(f'{parent_dir}/**/*_Solution.ipynb', recursive=True)

    assert_on_branch('questions')
    if verbose:
        print('Removing solution files...')
    for f in to_remove:
        execute(f'git rm -f {f}')


def execute(cmd, shell=True):
    out = subprocess.check_output(cmd, shell=True)
    if verbose:
        print(out.decode('utf-8'))


def add_question_into_commit(filename):
    if verbose:
        print(f'Adding {filename} to commit...')
    execute(f'git add {filename}')


def checkout_to_questions_branch():
    if verbose:
        print('Checking out to a new local branch...')
    execute("git checkout -b questions")


def commit_and_pull_repo(repo):
    if verbose:
        print('Committing changes...')
    execute("git commit -m 'Removes solutions'")
    if verbose:
        print(f'Pulling from github {repo} repo...')
    execute(f'git pull git@github.com:kaufmanno/{repo}.git main')


def clean_path(course):
    assert_on_branch('questions')
    if verbose:
        print(f'copying tools to {course}...')
    execute(f'cp tools/* ./{course}')
    if verbose:
        print(f'Moving files from {course}...')
    execute('find . -maxdepth 1 -type f -exec git rm {} \\;')
    # TODO remove subdirectories related to the other lectures
    execute(f'git mv ./{course}/.gitignore .')
    execute(f'git mv ./{course}/* .')
    if verbose:
        print(f'Removing {course} emptied subdirectory...')
    execute(f'rm -rf ./{course}')


def push_repo_and_remove_branch(repo):
    if verbose:
        print(f'Pushing to {repo}...')
    execute(f'git push git@github.com:kaufmanno/{repo}.git questions:main')
    if verbose:
        print(f'Stashing changes...')
    execute('git stash')
    if verbose:
        print(f'Checking out back to master...')
    execute('git checkout master')
    if verbose:
        print(f'Deleting questions branch...')
    execute('git branch -D questions')


def assert_on_branch(branch='master'):
    out = subprocess.check_output('git rev-parse --abbrev-ref HEAD', shell=True)
    if out.decode('utf-8').lower().strip('\n') != branch:
        print(f'Warning: You should be on branch {branch}. You\'re currently on {out.decode("utf-8")}. Quitting...')
        exit(1)


if __name__ == '__main__':
    assert_on_branch('master')

    repository = None
    if verbose:
        print('Starting...')

    course = sys.argv[1]
    section = sys.argv[2]
    topic = sys.argv[3]

    in_notebook = f'./{section}/{topic}/{topic}_Solution.ipynb'
    if verbose:
        print(f'Updating a question notebook from {in_notebook} in {course}...')

    # TODO: Add more courses with corresponding subdirectories and github folders in the list
    course_list = ['SIG']
    if course in course_list:
        checkout_to_questions_branch()
        assert_on_branch('questions')
        clean_path(course)
        question_filename = create_question(in_notebook)
        remove_solutions()
        add_question_into_commit(question_filename)
        commit_and_pull_repo(course)
        push_repo_and_remove_branch(course)
        assert_on_branch('master')
        print(f'Question successfully updated {topic} question notebook in section {section} of {course}...')
    else:
        print(f'Un')

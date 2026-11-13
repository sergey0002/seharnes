"""Static integration guardrails; not proof of agent compliance at runtime."""
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[8]
SKILLS_ROOT = REPO / '.agents' / 'skills'


def skill_dir(name):
    for path in SKILLS_ROOT.rglob('SKILL.md'):
        if path.parent.name == name:
            return path.parent
    raise FileNotFoundError(f'skill not found: {name}')


class SkillIntegrationTests(unittest.TestCase):
    def text(self, skill):
        return (skill_dir(skill) / 'SKILL.md').read_text(encoding='utf-8')

    def test_shared_context_has_one_owner(self):
        for skill in ('send-to-git', 'task-doc', 'task-report'):
            with self.subTest(skill=skill):
                text = self.text(skill)
                self.assertIn('workflow-context.json', text)
                self.assertNotIn('"$schema"', text)
        report = self.text('task-change-report')
        self.assertIn('workflow_contract.py', report)
        self.assertIn('assets/workflow-context.schema.json', report)

    def test_new_consent_is_not_push_consent(self):
        text = self.text('send-to-git')
        self.assertIn('Напишите да, если сделать', text)
        self.assertIn('Предыдущее согласие на push', text)
        self.assertIn('Частичный выбор пользователя ограничивает scope', text)

    def test_documentation_checks_before_writes(self):
        text = self.text('task-doc')
        self.assertLess(text.index('До создания/изменения документов'),
                        text.index('## Шаг B3'))
        self.assertIn('без HTML', text)
        self.assertIn('B4.5', text)

    def test_no_recursive_jira_publication(self):
        report = self.text('task-change-report')
        jira = self.text('task-report')
        self.assertIn('Не вызывай task-doc обратно', report)
        self.assertIn('В трекер ничего не отправлять', jira)
        self.assertIn('не вызывает обратно', jira)
        self.assertIn('не дублируются в чат', jira)

    def test_partial_consent_reaches_children(self):
        self.assertIn('без HTML', self.text('task-doc'))
        self.assertIn('без Jira', self.text('task-change-report'))
        self.assertIn('allowed_steps', self.text('task-change-report'))
        self.assertIn('не является новым разрешением',
                      self.text('task-change-report'))

    def test_hashes_are_not_truth(self):
        text = self.text('task-change-report')
        self.assertIn('Hash подтверждает неизменность, не истинность', text)
        self.assertIn('Не исправляй stale заменой', text)

    def test_quality_requirements_remain(self):
        report = self.text('task-change-report')
        for token in ('вопросы тимлида', 'evidence', 'Mermaid', 'report-model.json',
                      'Скриншоты', 'Jira', 'file://wsl.localhost/'):
            with self.subTest(token=token):
                self.assertIn(token, report)
        jira = self.text('task-report')
        for token in ('релиз', '3-5', 'Version', 'collect-shots.py'):
            self.assertIn(token, jira)


if __name__ == '__main__':
    unittest.main()

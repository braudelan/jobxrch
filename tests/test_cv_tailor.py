# tests/test_cv_tailor.py
import pytest
from src.cv_tailor import (
    render_cv,
    CVTailorResult,
    Bullet,
    ExperienceEntry,
    SkillCategory,
    Summary,
    _load_cv_template,
)


@pytest.fixture
def sample_cv_result() -> CVTailorResult:
    """Create a sample CVTailorResult for testing."""
    template = _load_cv_template()
    return CVTailorResult(
        header=template["header"],
        summary=Summary(
            text="Data-driven professional with 5+ years experience building scalable data infrastructure.",
            source_sections=["Summary", "Experience"],
        ),
        skills=[
            SkillCategory(
                category="Data Engineering",
                items="Python, SQL, Spark, Airflow, Snowflake",
                source_sections=["Skills"],
            ),
            SkillCategory(
                category="Leadership",
                items="Team mentoring, project management",
                source_sections=["Experience"],
            ),
        ],
        experience=[
            ExperienceEntry(
                company="Forter",
                title="Fraud Core Researcher",
                period="2022 – 2026",
                tagline="Led fraud detection research and pipeline optimization",
                bullets=[
                    Bullet(
                        title="Architecture Design",
                        text="Designed and implemented real-time fraud detection pipeline processing 10K+ transactions/sec",
                        source_sections=["Experience > Forter"],
                    ),
                    Bullet(
                        title="Performance Optimization",
                        text="Optimized core detection algorithms, reducing false positive rate by 25%",
                        source_sections=["Experience > Forter", "Skills"],
                    ),
                ],
                source_sections=["Experience > Forter"],
            ),
            ExperienceEntry(
                company="Weizmann Institute of Science",
                title="Data Analyst",
                period="2020 – 2021",
                tagline="Analyzed large-scale scientific datasets",
                bullets=[
                    Bullet(
                        title="Data Analysis",
                        text="Processed and analyzed 50GB+ of scientific data using Python and SQL",
                        source_sections=["Experience > Weizmann"],
                    ),
                ],
                source_sections=["Experience > Weizmann"],
            ),
        ],
        education=template["education"],
    )


class TestRenderCV:
    """Test suite for render_cv() function."""

    def test_render_produces_markdown(self, sample_cv_result):
        """Test that render_cv returns markdown string."""
        markdown = render_cv(sample_cv_result)
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_render_includes_header(self, sample_cv_result):
        """Test that header (name, title, contact) is rendered."""
        markdown = render_cv(sample_cv_result)
        header = sample_cv_result.header

        assert header["name"] in markdown
        assert header["title"] in markdown
        assert header["email"] in markdown
        assert header["phone"] in markdown
        assert header["linkedin"] in markdown

    def test_render_includes_summary(self, sample_cv_result):
        """Test that summary section is rendered."""
        markdown = render_cv(sample_cv_result)
        assert "## Summary" in markdown
        assert sample_cv_result.summary.text in markdown

    def test_render_includes_skills(self, sample_cv_result):
        """Test that skills section groups categories correctly."""
        markdown = render_cv(sample_cv_result)
        assert "## Skills" in markdown

        for skill in sample_cv_result.skills:
            assert skill.category in markdown
            assert skill.items in markdown

    def test_render_includes_experience(self, sample_cv_result):
        """Test that experience section includes companies, titles, periods."""
        markdown = render_cv(sample_cv_result)
        assert "## Experience" in markdown

        for exp in sample_cv_result.experience:
            assert exp.company in markdown
            if exp.title:
                assert exp.title in markdown
            assert exp.period in markdown
            assert exp.tagline in markdown

    def test_render_includes_experience_bullets(self, sample_cv_result):
        """Test that experience bullets are rendered with titles."""
        markdown = render_cv(sample_cv_result)

        for exp in sample_cv_result.experience:
            for bullet in exp.bullets:
                assert bullet.title in markdown
                assert bullet.text in markdown

    def test_render_includes_education(self, sample_cv_result):
        """Test that education section is rendered."""
        markdown = render_cv(sample_cv_result)
        assert "## Education" in markdown

        for edu in sample_cv_result.education:
            assert edu["degree"] in markdown
            assert edu["institution"] in markdown
            assert edu["year"] in markdown

    def test_render_markdown_hierarchy(self, sample_cv_result):
        """Test that markdown uses correct header hierarchy."""
        markdown = render_cv(sample_cv_result)

        # H1 for name
        assert f"# {sample_cv_result.header['name']}" in markdown
        # H2 for sections
        assert "## Summary" in markdown
        assert "## Skills" in markdown
        assert "## Experience" in markdown
        assert "## Education" in markdown
        # H3 for companies
        assert "###" in markdown

    def test_render_source_sections_not_in_output(self, sample_cv_result):
        """Test that source_sections fields are NOT rendered (llmEV only)."""
        markdown = render_cv(sample_cv_result)
        # source_sections should not appear in rendered markdown
        assert "source_sections" not in markdown.lower()

    def test_render_empty_summary(self, sample_cv_result):
        """Test rendering with empty summary text."""
        sample_cv_result.summary.text = ""
        markdown = render_cv(sample_cv_result)
        # Summary section should not appear if text is empty
        assert "## Summary" not in markdown

    def test_render_no_skills(self, sample_cv_result):
        """Test rendering with no skills."""
        sample_cv_result.skills = []
        markdown = render_cv(sample_cv_result)
        assert "## Skills" not in markdown

    def test_render_no_experience(self, sample_cv_result):
        """Test rendering with no experience."""
        sample_cv_result.experience = []
        markdown = render_cv(sample_cv_result)
        assert "## Experience" not in markdown

    def test_render_multiple_bullets_per_role(self, sample_cv_result):
        """Test rendering role with multiple bullets."""
        # Forter has 2 bullets
        markdown = render_cv(sample_cv_result)
        assert "Architecture Design" in markdown
        assert "Performance Optimization" in markdown

    def test_render_handles_optional_title(self, sample_cv_result):
        """Test rendering when role has no title (null)."""
        sample_cv_result.experience[0].title = None
        markdown = render_cv(sample_cv_result)
        # Should still render company and period
        assert sample_cv_result.experience[0].company in markdown
        assert sample_cv_result.experience[0].period in markdown

    def test_render_includes_education_note(self, sample_cv_result):
        """Test rendering education entry with optional note."""
        # Weizmann entry has a note
        markdown = render_cv(sample_cv_result)
        # Check for the note in any education entry that has one
        for edu in sample_cv_result.education:
            if "note" in edu and edu["note"]:
                assert edu["note"] in markdown


class TestCVTailorModels:
    """Test Pydantic model validation."""

    def test_bullet_model(self):
        """Test Bullet model."""
        bullet = Bullet(
            title="Achievement",
            text="Did something impressive",
            source_sections=["Experience", "Skills"],
        )
        assert bullet.title == "Achievement"
        assert len(bullet.source_sections) == 2

    def test_experience_entry_model(self):
        """Test ExperienceEntry model."""
        entry = ExperienceEntry(
            company="TestCorp",
            title="Engineer",
            period="2020-2024",
            tagline="Built things",
            bullets=[
                Bullet(title="Task1", text="Did task1", source_sections=["Exp"]),
            ],
            source_sections=["Experience"],
        )
        assert entry.company == "TestCorp"
        assert len(entry.bullets) == 1

    def test_experience_entry_optional_title(self):
        """Test ExperienceEntry with None title."""
        entry = ExperienceEntry(
            company="Freelance",
            title=None,
            period="2024",
            tagline="Independent work",
            bullets=[],
            source_sections=["Experience"],
        )
        assert entry.title is None

    def test_skill_category_model(self):
        """Test SkillCategory model."""
        skill = SkillCategory(
            category="Languages",
            items="Python, SQL, Go",
            source_sections=["Skills"],
        )
        assert skill.category == "Languages"
        assert "Python" in skill.items

    def test_summary_model(self):
        """Test Summary model."""
        summary = Summary(
            text="Experienced professional",
            source_sections=["Summary", "Experience"],
        )
        assert len(summary.source_sections) == 2

    def test_cv_tailor_result_model(self):
        """Test CVTailorResult model with full structure."""
        template = _load_cv_template()
        result = CVTailorResult(
            header=template["header"],
            summary=Summary(text="Test", source_sections=[]),
            skills=[],
            experience=[],
            education=template["education"],
        )
        assert result.header["name"] == "Elan Braude"
        assert len(result.education) == 3


class TestTemplateLoading:
    """Test template loading."""

    def test_load_cv_template(self):
        """Test that template loads and has required structure."""
        template = _load_cv_template()
        assert "header" in template
        assert "summary" in template
        assert "skills" in template
        assert "experience" in template
        assert "education" in template

    def test_template_header_structure(self):
        """Test template header has required fields."""
        template = _load_cv_template()
        header = template["header"]
        assert "name" in header
        assert "title" in header
        assert "email" in header
        assert "phone" in header
        assert "linkedin" in header

    def test_template_experience_structure(self):
        """Test template experience entries have correct structure."""
        template = _load_cv_template()
        for exp in template["experience"]:
            assert "company" in exp
            assert "period" in exp
            assert "bullets" in exp
            assert isinstance(exp["bullets"], list)

    def test_template_education_structure(self):
        """Test template education entries have required fields."""
        template = _load_cv_template()
        for edu in template["education"]:
            assert "degree" in edu
            assert "institution" in edu
            assert "year" in edu

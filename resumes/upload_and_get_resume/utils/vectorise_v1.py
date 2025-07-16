import os
import json
import re
from datetime import datetime
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import uuid

load_dotenv()
NEO4J_USER = os.environ.get('NEO4jUSER')
NEO4J_PASSWORD = os.environ.get('NEO4jPASSWORD')
NEO4J_URI = os.environ.get('NEO4jURI')
class Neo4jResumeProcessor:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self._ensure_na_node()
    
    def close(self):
        self.driver.close()
    
    def _ensure_na_node(self):
        """Ensure a single N/A node exists in the database"""
        with self.driver.session() as session:
            session.run("""
                MERGE (na:NAValue {name: 'N/A'})
                ON CREATE SET na.created = datetime()
            """)
    # Get Embeddings
    async def get_embedding(self, text):
        """Generate embedding for given text"""
        try:
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            print(f"[ERROR] Local embedding failed: {e}")
            raise e
    # Create Indexes
    def create_indexes(self):
        """Create necessary indexes for better performance"""
        with self.driver.session() as session:
            # Create indexes
            indexes = [
                "CREATE INDEX candidate_email_index IF NOT EXISTS FOR (c:Candidate) ON (c.email)",
                "CREATE INDEX company_name_index IF NOT EXISTS FOR (comp:Company) ON (comp.companyName)",
                "CREATE INDEX skill_name_index IF NOT EXISTS FOR (s:Skill) ON (s.skillName)",
                "CREATE INDEX location_name_index IF NOT EXISTS FOR (l:Location) ON (l.name)",
                "CREATE INDEX education_institution_index IF NOT EXISTS FOR (e:Education) ON (e.institutionName)",
                "CREATE INDEX role_name_index IF NOT EXISTS FOR (r:Role) ON (r.roleName)",
                "CREATE INDEX language_name_index IF NOT EXISTS FOR (lang:Language) ON (lang.languageName)",
                "CREATE INDEX link_url_index IF NOT EXISTS FOR (l:Link) ON (l.url)",
                "CREATE INDEX link_platform_index IF NOT EXISTS FOR (l:Link) ON (l.platform)",
                "CREATE INDEX designation_name_index IF NOT EXISTS FOR (d:Designation) ON (d.name)",
                "CREATE INDEX na_value_index IF NOT EXISTS FOR (na:NAValue) ON (na.name)"
            ]
            
            for index in indexes:
                try:
                    session.run(index)
                    print(f"Created index: {index.split('FOR')[1].split('ON')[0].strip()}")
                except Exception as e:
                    print(f"Index creation failed or already exists: {e}")
    
    def clean_text(self, text):
        """Clean text by removing extra whitespace and normalizing"""
        if not text:
            return None
        text = text.strip()
        # Check for N/A with or without explanation in brackets
        if re.match(r'^n/?a\s*(\([^)]*\))?$', text.lower()):
            return 'N/A'
        if text.lower() in ['null', 'none', '']:
            return None
        return text
    
    def parse_resume_data(self, resume_text):
        """Parse structured resume data from new format"""
        data = {
            'personal_info': {},
            'education': [],
            'skills': [],
            'languages': [],
            'achievements': [],
            'projects': [],
            'suitable_roles': [],
            'employers': [],
            'links': []
        }
        
        # Extract sections
        sections = self._extract_sections(resume_text)
        
        # Parse candidate profile section
        if 'CANDIDATE PROFILE' in sections:
            data['personal_info'] = self._parse_candidate_profile(sections['CANDIDATE PROFILE'])
        
        # Parse education section
        if 'EDUCATION' in sections:
            data['education'] = self._parse_education_new_format(sections['EDUCATION'])
        
        # Parse skills section
        if 'SKILLS' in sections:
            data['skills'] = self._parse_skills_new_format(sections['SKILLS'])
        
        # Parse other sections
        if 'LANGUAGES' in sections:
            data['languages'] = self._parse_simple_list_section(sections['LANGUAGES'])
        
        if 'ACHIEVEMENTS' in sections:
            data['achievements'] = self._parse_simple_list_section(sections['ACHIEVEMENTS'])
        
        if 'PROJECTS' in sections:
            data['projects'] = self._parse_projects_new_format(sections['PROJECTS'])
        
        if 'SUITABLE ROLES' in sections:
            data['suitable_roles'] = self._parse_simple_list_section(sections['SUITABLE ROLES'])
        
        if 'LINKS' in sections:
            data['links'] = self._parse_links_new_format(sections['LINKS'])
        
        return data
    
    def _extract_sections(self, resume_text):
        """Extract sections from resume text"""
        sections = {}
        current_section = None
        current_content = []
        
        lines = resume_text.split('\n')
        for line in lines:
            # Check if it's a section header
            if line.strip().startswith('===') and line.strip().endswith('==='):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                
                # Extract new section name
                section_name = line.strip().replace('===', '').strip()
                current_section = section_name
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    def _parse_candidate_profile(self, profile_text):
        """Parse candidate profile section"""
        personal_info = {}
        
        patterns = {
            'name': r'Name:\s*(.*?)(?:\n|$)',
            'gender': r'Gender:\s*(.*?)(?:\n|$)',
            'age': r'Age:\s*(.*?)(?:\n|$)',
            'email': r'E-mail:\s*(.*?)(?:\n|$)',
            'phone': r'Phone number:\s*(.*?)(?:\n|$)',
            'location': r'Location:\s*(.*?)(?:\n|$)',
            'preferred_location': r'Preferred Location:\s*(.*?)(?:\n|$)',
            'years_experience': r'Years of Experience:\s*(\d+\.?\d*)',
            'current_designation': r'Current/Last Designation:\s*(.*?)(?:\n|$)',
            'current_employer': r'Current/Last Employer:\s*(.*?)(?:\n|$)',
            'expected_ctc': r'Expected CTC:\s*(.*?)(?:\n|$)',
            'current_ctc': r'Current CTC:\s*(.*?)(?:\n|$)',
            'previous_employer': r'Previous Employer:\s*(.*?)(?:\n|$)',
            'interests_hobbies': r'Interests/Hobbies:\s*(.*?)(?:\n|$)',
            'current_notice_period': r'Current Notice Period:\s*(.*?)(?:\n|$)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, profile_text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = self.clean_text(match.group(1))
                if value and value != 'N/A':
                    personal_info[key] = value
        
        # Handle previous employers separately (can be multi-line)
        if 'previous_employer' in patterns:
            prev_emp_match = re.search(r'Previous Employer:\s*(.*?)(?=\n[A-Z]|\n===|$)', 
                                     profile_text, re.IGNORECASE | re.DOTALL)
            if prev_emp_match:
                employers_text = prev_emp_match.group(1)
                employers = []
                for line in employers_text.split('\n'):
                    cleaned = self.clean_text(line.strip('- ').strip())
                    if cleaned and cleaned != 'N/A':
                        employers.append(cleaned)
                if employers:
                    personal_info['previous_employers'] = employers
        
        return personal_info
    
    def _parse_education_new_format(self, education_text):
        """Parse education section in new format"""
        education_list = []
        current_institution = None
        current_entry = {}
        
        lines = education_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if it's an institution line (not starting with -)
            if not line.startswith('-') and ':' in line:
                # Save previous entry
                if current_entry and 'institution' in current_entry:
                    education_list.append(current_entry.copy())
                
                # Start new entry
                inst_match = re.search(r'Institution:\s*(.*?)(?:,|$)', line)
                if inst_match:
                    current_institution = self.clean_text(inst_match.group(1))
                    if current_institution and current_institution != 'N/A':
                        current_entry = {'institution': current_institution}
            
            # Parse sub-items
            elif line.startswith('-') and current_entry:
                if 'Degree/Program:' in line:
                    degree_match = re.search(r'Degree/Program:\s*(.*?)$', line)
                    if degree_match:
                        degree = self.clean_text(degree_match.group(1))
                        if degree and degree != 'N/A':
                            current_entry['degree'] = degree
                
                elif 'Grades/CGPA/Percentage:' in line:
                    grade_match = re.search(r'Grades/CGPA/Percentage:\s*(.*?)$', line)
                    if grade_match:
                        grades = self.clean_text(grade_match.group(1))
                        if grades and grades != 'N/A':
                            current_entry['grades'] = grades
                
                elif 'Year of Passing:' in line:
                    year_match = re.search(r'Year of Passing:\s*(.*?)$', line)
                    if year_match:
                        year = self.clean_text(year_match.group(1))
                        if year and year != 'N/A':
                            current_entry['year'] = year
        
        # Add last entry
        if current_entry and 'institution' in current_entry:
            education_list.append(current_entry)
        
        return education_list
    
    def _parse_skills_new_format(self, skills_text):
        """Parse skills section in new format"""
        skills_list = []
        current_category = None
        
        lines = skills_text.strip().split('\n')
        for line in lines:
            original_line = line
            line = line.strip()
            
            if not line:
                continue
            
            # Calculate indentation
            indent_level = len(original_line) - len(original_line.lstrip())
            
            # Check if it's a category (ends with colon or is a header)
            if line.endswith(':'):
                category_name = line.rstrip(':').strip('* ').strip()
                if category_name and category_name != 'N/A':
                    current_category = category_name
                continue
            
            # It's a skill - remove bullets and markers
            skill_name = re.sub(r'^[\s\-\*\•]+', '', line).strip()
            skill_name = self.clean_text(skill_name)
            
            if skill_name and skill_name != 'N/A' and len(skill_name) > 1:
                skills_list.append({
                    'name': skill_name,
                    'category': current_category or 'General',
                    'subcategory': None
                })
        
        return skills_list
    
    def _parse_simple_list_section(self, section_text):
        """Parse simple list sections"""
        items = []
        
        for line in section_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Remove markers
            cleaned = re.sub(r'^[\s\-\*\•]+', '', line).strip()
            cleaned = self.clean_text(cleaned)
            
            if cleaned and cleaned != 'N/A' and cleaned not in items:
                items.append(cleaned)
        
        return items
    
    def _parse_projects_new_format(self, projects_text):
        """Parse projects section in new format"""
        projects = []
        
        # Split by numbered items or bullet points
        lines = projects_text.strip().split('\n')
        current_project = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if it's a numbered project or bullet
            if re.match(r'^\d+\.', line) or line.startswith('*') or line.startswith('-'):
                # Remove number/bullet and clean
                project = re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
                project = self.clean_text(project)
                if project and project != 'N/A':
                    projects.append(project)
            else:
                # Could be continuation of previous project
                cleaned = self.clean_text(line)
                if cleaned and cleaned != 'N/A' and projects:
                    projects[-1] += f" {cleaned}"
        
        return projects
    
    def _parse_links_new_format(self, links_text):
        """Parse links section in new format"""
        links = []
        
        # Match pattern like [Link Text]: URL or - Link Text: URL
        lines = links_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Pattern 1: [Link Text]: URL
            match1 = re.match(r'\[(.*?)\]:\s*(.*?)$', line)
            if match1:
                link_type = self.clean_text(match1.group(1))
                link_url = self.clean_text(match1.group(2))
                if link_type and link_url and link_url != 'N/A':
                    links.append({
                        'type': link_type,
                        'url': link_url,
                        'original': line
                    })
                continue
            
            # Pattern 2: - Link Text: URL
            match2 = re.match(r'^[\-\*]\s*(.*?):\s*(.*?)$', line)
            if match2:
                link_type = self.clean_text(match2.group(1))
                link_url = self.clean_text(match2.group(2))
                if link_type and link_url and link_url != 'N/A':
                    links.append({
                        'type': link_type,
                        'url': link_url,
                        'original': line
                    })
                continue
            
            # Pattern 3: Direct URL or email
            cleaned = self.clean_text(line.strip('- ').strip('* ').strip())
            if cleaned and cleaned != 'N/A':
                if '@' in cleaned:
                    links.append({
                        'type': 'Email',
                        'url': cleaned,
                        'original': line
                    })
                elif any(domain in cleaned.lower() for domain in ['http://', 'https://', '.com', '.org', '.net']):
                    link_type = 'Other'
                    if 'linkedin' in cleaned.lower():
                        link_type = 'LinkedIn'
                    elif 'github' in cleaned.lower():
                        link_type = 'GitHub'
                    
                    links.append({
                        'type': link_type,
                        'url': cleaned,
                        'original': line
                    })
        
        return links
    # Store Resume To Neo4J 
    async def store_resume_to_neo4j(self, resume_text, resume_file_path, json_file_path, years_of_experience):
        """Store resume data in Neo4j graph database By making Nodes and extablish relationships(edge) between them """
        try:
            # Generate embedding for the entire resume text
            embedding = await self.get_embedding(resume_text)
            
            # Parse resume data
            data = self.parse_resume_data(resume_text)
            
            # Generate unique candidate ID
            candidate_id = str(uuid.uuid4())
            
            with self.driver.session() as session:
                # Create candidate node
                candidate_query = """
                CREATE (c:Candidate {
                    candidateId: $candidate_id,
                    name: $name,
                    email: $email,
                    phoneNumber: $phone,
                    yearsOfExperience: $years_exp,
                    resumePath: $resume_path,
                    jsonPath: $json_path,
                    embedding: $embedding,
                    createdDate: $created_date
                })
                RETURN c.candidateId as candidateId
                """
                
                personal_info = data['personal_info']
                result = session.run(candidate_query, {
                    'candidate_id': candidate_id,
                    'name': personal_info.get('name', 'Unknown'),
                    'email': personal_info.get('email'),
                    'phone': personal_info.get('phone'),
                    'years_exp': float(years_of_experience),
                    'resume_path': resume_file_path,
                    'json_path': json_file_path,
                    'embedding': embedding,
                    'created_date': datetime.now().isoformat()
                })
                
                created_candidate_id = result.single()['candidateId']
                print(f"Created candidate: {personal_info.get('name', 'Unknown')} with ID: {created_candidate_id}")
                
                # Process all relationships
                await self._process_locations(session, created_candidate_id, personal_info)
                await self._process_companies(session, created_candidate_id, personal_info)
                await self._process_designation(session, created_candidate_id, personal_info)
                await self._process_education(session, created_candidate_id, data['education'])
                await self._process_skills(session, created_candidate_id, data['skills'])
                await self._process_languages(session, created_candidate_id, data['languages'])
                await self._process_achievements(session, created_candidate_id, data['achievements'])
                await self._process_projects(session, created_candidate_id, data['projects'])
                await self._process_suitable_roles(session, created_candidate_id, data['suitable_roles'])
                await self._process_links(session, created_candidate_id, data['links'])
                
                # Handle N/A relationships for missing data
                await self._process_na_relationships(session, created_candidate_id, personal_info, data)
                
                print(f"Successfully stored resume data for {personal_info.get('name', 'Unknown')}")
                return created_candidate_id
                
        except Exception as e:
            print(f"[ERROR] Unable to store in Neo4j: {e}")
            raise e
    # Process Locations (Async)
    async def _process_locations(self, session, candidate_id, personal_info):
        """Process location information"""
        locations = []
        
        if personal_info.get('location'):
            locations.append(('current', personal_info['location']))
        if personal_info.get('preferred_location'):
            locations.append(('preferred', personal_info['preferred_location']))
        
        for location_type, location_str in locations:
            # Parse location (City, State format)
            parts = [part.strip() for part in location_str.split(',')]
            city = parts[0] if parts else location_str
            state = parts[1] if len(parts) > 1 else None
            country = parts[2] if len(parts) > 2 else None
            
            # Create or get location node
            location_query = """
            MERGE (l:Location {name: $location_name})
            ON CREATE SET l.city = $city, l.state = $state, l.country = $country, l.locationId = randomUUID()
            RETURN l.locationId as locationId
            """
            
            session.run(location_query, {
                'location_name': location_str,
                'city': city,
                'state': state,
                'country': country
            })
            
            # Create relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (l:Location {name: $location_name})
            CREATE (c)-[:LOCATED_IN {locationType: $location_type}]->(l)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'location_name': location_str,
                'location_type': location_type
            })
    # Process Companies (Async)
    async def _process_companies(self, session, candidate_id, personal_info):
        """Process company information with different relationships"""
        # Process current/last employer
        current_employer = personal_info.get('current_employer')
        if current_employer:
            # Create company node
            company_query = """
            MERGE (comp:Company {companyName: $company_name})
            ON CREATE SET comp.companyId = randomUUID()
            RETURN comp.companyId as companyId
            """
            session.run(company_query, {'company_name': current_employer})
            
            # Create WORKING_WORKED_AT relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (comp:Company {companyName: $company_name})
            CREATE (c)-[:WORKING_WORKED_AT {
                isCurrent: true,
                designation: $designation
            }]->(comp)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'company_name': current_employer,
                'designation': personal_info.get('current_designation')
            })
        
        # Process previous employers
        previous_employers = personal_info.get('previous_employers', [])
        for i, employer in enumerate(previous_employers):
            if employer and employer != 'N/A':
                # Create company node
                company_query = """
                MERGE (comp:Company {companyName: $company_name})
                ON CREATE SET comp.companyId = randomUUID()
                RETURN comp.companyId as companyId
                """
                session.run(company_query, {'company_name': employer})
                
                # Create WORKED_AT relationship
                rel_query = """
                MATCH (c:Candidate {candidateId: $candidate_id})
                MATCH (comp:Company {companyName: $company_name})
                CREATE (c)-[:WORKED_AT {
                    isCurrent: false,
                    order: $order
                }]->(comp)
                """
                
                session.run(rel_query, {
                    'candidate_id': candidate_id,
                    'company_name': employer,
                    'order': i
                })
    # Process Designation (Async)
    async def _process_designation(self, session, candidate_id, personal_info):
        """Process designation information"""
        designation = personal_info.get('current_designation')
        if designation:
            # Create designation node
            designation_query = """
            MERGE (d:Designation {name: $designation_name})
            ON CREATE SET d.designationId = randomUUID()
            RETURN d.designationId as designationId
            """
            session.run(designation_query, {'designation_name': designation})
            
            # Create relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (d:Designation {name: $designation_name})
            CREATE (c)-[:HAS_DESIGNATION {
                isCurrent: true,
                company: $company
            }]->(d)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'designation_name': designation,
                'company': personal_info.get('current_employer')
            })
    # Process education (Async)
    async def _process_education(self, session, candidate_id, education_list):
        """Process education information"""
        for edu in education_list:
            if not edu.get('institution'):
                continue
            
            # Create or get education node
            edu_query = """
            MERGE (e:Education {
                institutionName: $institution,
                degree: $degree
            })
            ON CREATE SET 
                e.educationId = randomUUID(),
                e.grades = $grades
            RETURN e.educationId as educationId
            """
            
            session.run(edu_query, {
                'institution': edu['institution'],
                'degree': edu.get('degree', 'Unknown'),
                'grades': edu.get('grades')
            })
            
            # Create relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (e:Education {institutionName: $institution, degree: $degree})
            CREATE (c)-[:STUDIED_AT {
                graduationYear: $year,
                grades: $grades
            }]->(e)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'institution': edu['institution'],
                'degree': edu.get('degree', 'Unknown'),
                'year': edu.get('year'),
                'grades': edu.get('grades')
            })
    # Process Skills (Async)
    async def _process_skills(self, session, candidate_id, skills_list):
        """Process skills information with categories"""
        for skill_info in skills_list:
            if not skill_info or not skill_info.get('name'):
                continue
            
            skill_name = skill_info['name']
            skill_category = skill_info.get('category', 'General')
            
            # Create or get skill node
            skill_query = """
            MERGE (s:Skill {skillName: $skill_name})
            ON CREATE SET 
                s.skillId = randomUUID(), 
                s.category = $category,
                s.createdDate = $created_date
            RETURN s.skillId as skillId
            """
            
            session.run(skill_query, {
                'skill_name': skill_name,
                'category': skill_category,
                'created_date': datetime.now().isoformat()
            })
            
            # Create relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (s:Skill {skillName: $skill_name})
            CREATE (c)-[:HAS_SKILL {
                category: $category,
                acquiredDate: $acquired_date
            }]->(s)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'skill_name': skill_name,
                'category': skill_category,
                'acquired_date': datetime.now().isoformat()
            })

    # Process Languages (Async)
    async def _process_languages(self, session, candidate_id, languages_list):
        """Process languages information"""
        for language in languages_list:
            if not language or language == 'N/A':
                continue
            
            # Create or get language node
            lang_query = """
            MERGE (lang:Language {languageName: $language_name})
            ON CREATE SET lang.languageId = randomUUID()
            RETURN lang.languageId as languageId
            """
            
            session.run(lang_query, {'language_name': language})
            
            # Create relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (lang:Language {languageName: $language_name})
            CREATE (c)-[:SPEAKS]->(lang)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'language_name': language
            })
    
    # Process Achivements (Async)
    async def _process_achievements(self, session, candidate_id, achievements_list):
        """Process achievements information"""
        for achievement in achievements_list:
            if not achievement or achievement == 'N/A':
                continue
            
            # Create achievement node
            ach_query = """
            CREATE (a:Achievement {
                achievementId: randomUUID(),
                title: $title,
                description: $description
            })
            WITH a
            MATCH (c:Candidate {candidateId: $candidate_id})
            CREATE (c)-[:ACHIEVED]->(a)
            """
            
            session.run(ach_query, {
                'candidate_id': candidate_id,
                'title': achievement[:100] + '...' if len(achievement) > 100 else achievement,
                'description': achievement
            })
    
    # Process Projects (Async)
    async def _process_projects(self, session, candidate_id, projects_list):
        """Process projects information"""
        for project in projects_list:
            if not project or project == 'N/A':
                continue
            
            # Create project node
            proj_query = """
            CREATE (p:Project {
                projectId: randomUUID(),
                projectName: $name,
                description: $description
            })
            WITH p
            MATCH (c:Candidate {candidateId: $candidate_id})
            CREATE (c)-[:WORKED_ON]->(p)
            """
            
            session.run(proj_query, {
                'candidate_id': candidate_id,
                'name': project[:100] + '...' if len(project) > 100 else project,
                'description': project
            })
    
    # Process Suitable Roles (Async)
    async def _process_suitable_roles(self, session, candidate_id, roles_list):
        """Process suitable roles information"""
        for role in roles_list:
            if not role or role == 'N/A':
                continue
            
            # Create or get role node
            role_query = """
            MERGE (r:Role {roleName: $role_name})
            ON CREATE SET r.roleId = randomUUID()
            RETURN r.roleId as roleId
            """
            
            session.run(role_query, {'role_name': role})
            
            # Create relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (r:Role {roleName: $role_name})
            CREATE (c)-[:SUITABLE_FOR]->(r)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'role_name': role
            })
    
    # Process Links (Async)
    async def _process_links(self, session, candidate_id, links_list):
        """Process links information"""
        for link_info in links_list:
            if not link_info or not link_info.get('url'):
                continue
            
            link_type = link_info.get('type', 'Other')
            link_url = link_info.get('url')
            
            # Create or get link node
            link_query = """
            MERGE (l:Link {url: $url})
            ON CREATE SET 
                l.linkId = randomUUID(),
                l.linkType = $link_type,
                l.platform = $platform,
                l.createdDate = $created_date
            RETURN l.linkId as linkId
            """
            
            # Determine platform
            platform = link_type
            
            session.run(link_query, {
                'url': link_url,
                'link_type': link_type,
                'platform': platform,
                'created_date': datetime.now().isoformat()
            })
            
            # Create relationship
            rel_query = """
            MATCH (c:Candidate {candidateId: $candidate_id})
            MATCH (l:Link {url: $url})
            CREATE (c)-[:HAS_LINK {
                linkType: $link_type,
                addedDate: $added_date
            }]->(l)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'url': link_url,
                'link_type': link_type,
                'added_date': datetime.now().isoformat()
            })
    
    # Process N/A Relationships (Async)
    async def _process_na_relationships(self, session, candidate_id, personal_info, data):
        """Create relationships to N/A node for missing data"""
        # Check for N/A values in personal info
        na_fields = []
        
        # Personal info N/A checks
        if personal_info.get('age') == 'N/A':
            na_fields.append(('age', 'HAS_AGE'))
        if personal_info.get('gender') == 'N/A':
            na_fields.append(('gender', 'HAS_GENDER'))
        if personal_info.get('preferred_location') == 'N/A':
            na_fields.append(('preferred_location', 'PREFERS_LOCATION'))
        if personal_info.get('expected_ctc') == 'N/A':
            na_fields.append(('expected_ctc', 'EXPECTS_CTC'))
        if personal_info.get('current_ctc') == 'N/A':
            na_fields.append(('current_ctc', 'HAS_CURRENT_CTC'))
        if personal_info.get('interests_hobbies') == 'N/A':
            na_fields.append(('interests_hobbies', 'HAS_INTERESTS'))
        if personal_info.get('current_notice_period') == 'N/A':
            na_fields.append(('current_notice_period', 'HAS_NOTICE_PERIOD'))
        
        # Check if entire sections are N/A or empty
        if not data.get('languages') or (len(data['languages']) == 1 and data['languages'][0] == 'N/A'):
            na_fields.append(('languages', 'SPEAKS'))
        if not data.get('projects') or (len(data['projects']) == 1 and data['projects'][0] == 'N/A'):
            na_fields.append(('projects', 'WORKED_ON'))
        if not data.get('achievements') or (len(data['achievements']) == 1 and data['achievements'][0] == 'N/A'):
            na_fields.append(('achievements', 'ACHIEVED'))
        
        # Create relationships to N/A node
        for field_name, relationship_type in na_fields:
            rel_query = f"""
            MATCH (c:Candidate {{candidateId: $candidate_id}})
            MATCH (na:NAValue {{name: 'N/A'}})
            CREATE (c)-[:{relationship_type} {{field: $field}}]->(na)
            """
            
            session.run(rel_query, {
                'candidate_id': candidate_id,
                'field': field_name
            })

# Store Resume To Neo4J
async def store_resume_to_neo4j(details, resume_file_path, json_file_path, years_of_experience):
    # Initialize processor
    processor = Neo4jResumeProcessor(
        uri=NEO4J_URI,
        user=NEO4J_USER, 
        password=NEO4J_PASSWORD
    )
    
    # Create indexes
    processor.create_indexes()
    
    try:
        # Store resume in Neo4j
        candidate_id = await processor.store_resume_to_neo4j(
            resume_text=details,
            years_of_experience=years_of_experience,
            resume_file_path=resume_file_path,
            json_file_path=json_file_path
        )
        print(f"Successfully processed candidate with ID: {candidate_id}")
        
    except Exception as e:
        print(f"Error processing resume: {e}")
    
    finally:
        processor.close()

# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(store_resume_to_neo4j())
import os
import json
import re
from datetime import datetime
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
NEO4jURI = os.environ.get('NEO4jURI')
NEO4jUSER = os.environ.get('NEO4jUSER')
NEO4jPASSWORD = os.environ.get('NEO4jPASSWORD')

# Candidate Search Engine Class
class CandidateSearchEngine:
    def __init__(self, uri=NEO4jURI, user=NEO4jUSER, password=NEO4jPASSWORD):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def close(self):
        self.driver.close()

    # Get Embedding (Async)
    async def get_embedding(self, text):
        """Generate embedding for given text"""
        try:
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            print(f"[ERROR] Embedding generation failed: {e}")
            raise e
    # Calculate Similarity from embedding/vector data
    def calculate_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings"""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    # Search Candidates (Async)
    async def search_candidates(
        self,
        search_params: Dict[str, Any],
        from_experience: float = 0,
        to_experience: Optional[float] = None,
        top_k: int = 20,
        similarity_threshold = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Search candidates based on multiple criteria including similarity search

        Args:
            search_params: Dictionary containing search criteria
                - skills: List of skills to search
                - role: List of roles to search (current and suitable)
                - location: List of locations to search
                - email: Email to search
                - phone: Phone number to search
                - education: List of education criteria
                - name: Name to search
            from_experience: Minimum years of experience
            to_experience: Maximum years of experience (None for no upper limit)
            top_k: Number of top candidates to return

        Returns:
            List of candidates with match scores
        """

        search_text_parts = []

        if "skills" in search_params and search_params["skills"]:
            search_text_parts.append(f"Skills: {', '.join(search_params['skills'])}")

        if "role" in search_params and search_params["role"]:
            search_text_parts.append(f"Role: {', '.join(search_params['role'])}")

        if "location" in search_params and search_params["location"]:
            search_text_parts.append(
                f"Location: {', '.join(search_params['location'])}"
            )
        if "name" in search_params and search_params["name"]:
            search_text_parts.append(f"Name: {', '.join(search_params['name'])}")
        if "phone" in search_params and search_params["phone"]:
            search_text_parts.append(f"Phone: {', '.join(search_params['phone'])}")
        if "email" in search_params and search_params["email"]:
            search_text_parts.append(f"Email: {', '.join(search_params['email'])}")

        search_text = " ".join(search_text_parts)

        search_embedding = (
            await self.get_embedding(search_text) if search_text else None
        )

        # Build and execute the search query
        candidates = await self._execute_search_query(
            search_params, from_experience, to_experience, search_embedding,similarity_threshold
        )

        # Sort candidates by total score and return top_k
        sorted_candidates = sorted(
            candidates, key=lambda x: x["total_score"], reverse=True
        )
        return sorted_candidates[:top_k]
    
    # Execute Search Query (Async)
    async def _execute_search_query(
        self,
        search_params: Dict[str, Any],
        from_experience: float,
        to_experience: Optional[float],
        search_embedding: Optional[List[float]],
        similarity_threshold=0.4
    ) -> List[Dict[str, Any]]:
        """Execute the search query and calculate scores"""

        # with self.driver.session() as session:
        #     results = session.run(
        #         """
        #             MATCH (c:Candidate)
        #             WHERE c.yearsOfExperience >= 0
        #             AND c.yearsOfExperience <= 999
        #             AND toLower(c.email) CONTAINS toLower('@gmail.com')
        #             AND c.phoneNumber CONTAINS '+9185'
        #             AND toLower(c.name) CONTAINS toLower('Aagam Sheth')
        #             RETURN c.name
        #         """
        #     )
        #     for record in results:
        #         print(record)
        with self.driver.session() as session:
            # Build the main query
            query = self._build_search_query(
                search_params, from_experience, to_experience
            )
            # print(
            #     "Query parameters:",
            #     {
            #         "from_exp": from_experience,
            #         "to_exp": to_experience if to_experience else 999,
            #         **self._prepare_query_params(search_params),
            #     },
            # )

            # Execute query
            results = session.run(
                query,
                {
                    "from_exp": from_experience,
                    "to_exp": to_experience if to_experience else 999,
                    **self._prepare_query_params(search_params),
                },
            )

            candidates = []
            for record in results:
                candidate_data = dict(record["candidate"])

                # Calculate match scores
                scores = self._calculate_match_scores(
                    record,
                    search_params,
                    search_embedding,
                    candidate_data.get("embedding"),
                )
                
                # Prepare candidate result
                
                if scores["total_score"] >= similarity_threshold:
                    # if True:
                    candidate_result = {
                        "candidate_id": candidate_data.get("candidateId"),
                        "name": candidate_data.get("name"),
                        "email": candidate_data.get("email"),
                        "phone": candidate_data.get("phoneNumber"),
                        "years_experience": candidate_data.get("yearsOfExperience"),
                        "resume_path": candidate_data.get("resumePath"),
                        "json_path": candidate_data.get("jsonPath"),
                        "matched_skills": record.get("matched_skills", []),
                        "total_skills": record.get("total_skills", []),
                        "matched_roles": record.get("matched_roles", []),
                        "current_designation": record.get("current_designation"),
                        "locations": record.get("locations", []),
                        "education": record.get("education", []),
                        "companies": record.get("companies", []),
                        # "current_company": record.get("companies", [None,'Fresher'])[0],
                        **scores,
                    }

                    candidates.append(candidate_result)

            return candidates
    # Build Search Query
    def _build_search_query(
        self,
        search_params: Dict[str, Any],
        from_experience: float,
        to_experience: Optional[float],
    ) -> str:
        """Build the Cypher query for searching candidates"""

        query_parts = []

        # Base query
        query_parts.append(
            """
        MATCH (c:Candidate)
        WHERE c.yearsOfExperience >= $from_exp
        """
        )

        if to_experience is not None and to_experience > 0:
            query_parts.append("AND c.yearsOfExperience <= $to_exp")

        if "email" in search_params and search_params["email"]:
            query_parts.append("AND toLower(c.email) CONTAINS toLower($email)")

        if "phone" in search_params and search_params["phone"]:

            query_parts.append("AND c.phoneNumber CONTAINS ($phone)")

        if "name" in search_params and search_params["name"]:
            query_parts.append("AND toLower(c.name) CONTAINS toLower($name)")

        # Collect additional data
        query_parts.append(
            """
        // Collect skills
        OPTIONAL MATCH (c)-[:HAS_SKILL]->(s:Skill)
        WITH c, collect(DISTINCT s.skillName) as all_skills
        
        // Collect matched skills if searching by skills
        """
        )

        if "skills" in search_params and search_params["skills"]:
            query_parts.append(
                """
            OPTIONAL MATCH (c)-[:HAS_SKILL]->(ms:Skill)
            WHERE toLower(ms.skillName) IN $skills_lower
            WITH c, all_skills, collect(DISTINCT ms.skillName) as matched_skills
            """
            )
        else:
            query_parts.append("WITH c, all_skills, [] as matched_skills")

        # Collect roles (current designation and suitable roles)
        query_parts.append(
            """
        // Collect current designation
        OPTIONAL MATCH (c)-[:HAS_DESIGNATION]->(d:Designation)
        WITH c, all_skills, matched_skills, d.name as current_designation
        
        // Collect suitable roles
        OPTIONAL MATCH (c)-[:SUITABLE_FOR]->(r:Role)
        WITH c, all_skills, matched_skills, current_designation, 
             collect(DISTINCT r.roleName) as suitable_roles
        
        // Combine current designation and suitable roles
        WITH c, all_skills, matched_skills, current_designation, suitable_roles,
             CASE 
                WHEN current_designation IS NOT NULL 
                THEN [current_designation] + suitable_roles 
                ELSE suitable_roles 
             END as all_roles
        """
        )

        # Match roles if searching by roles
        if "role" in search_params and search_params["role"]:
            query_parts.append(
                """
            WITH c, all_skills, matched_skills, current_designation, all_roles,
                 [role in $roles_lower WHERE 
                  ANY(candidate_role in all_roles WHERE 
                      toLower(candidate_role) CONTAINS role OR 
                      role CONTAINS toLower(candidate_role)
                  )
                 ] as matched_roles
            """
            )
        else:
            query_parts.append(
                "WITH c, all_skills, matched_skills, current_designation, all_roles, [] as matched_roles"
            )

        # Collect locations
        query_parts.append(
            """
        // Collect locations
        OPTIONAL MATCH (c)-[:LOCATED_IN]->(l:Location)
        WITH c, all_skills, matched_skills, current_designation, all_roles, matched_roles,
             collect(DISTINCT {
                 name: l.name, 
                 city: l.city, 
                 state: l.state,
                 country: l.country,
                 type: CASE 
                     WHEN EXISTS((c)-[:LOCATED_IN {locationType: 'current'}]->(l)) 
                     THEN 'current' 
                     ELSE 'preferred' 
                 END
             }) as locations
        """
        )

        # Collect education
        query_parts.append(
            """
        // Collect education
        OPTIONAL MATCH (c)-[:STUDIED_AT]->(e:Education)
        WITH c, all_skills, matched_skills, current_designation, all_roles, matched_roles, locations,
             collect(DISTINCT {
                 institution: e.institutionName,
                 degree: e.degree,
                 grades: e.grades
             }) as education
        """
        )

        # Collect companies
        query_parts.append(
            """
        // Collect companies
        OPTIONAL MATCH (c)-[:WORKED_AT|WORKING_WORKED_AT]->(comp:Company)
        WITH c, all_skills, matched_skills, current_designation, all_roles, matched_roles, 
             locations, education,
             collect(DISTINCT comp.companyName) as companies
        """
        )
        if "location" in search_params and search_params["location"] or "education" in search_params and search_params["education"]:
            if "education" in search_params and search_params["education"] and "location" in search_params and search_params["location"]:
                query_parts.append(
                """
                WHERE ANY(loc IN locations WHERE 
                    ANY(search_loc IN $locations_lower WHERE 
                        toLower(loc.name) CONTAINS search_loc OR
                        toLower(loc.city) CONTAINS search_loc OR
                        toLower(loc.state) CONTAINS search_loc OR
                        toLower(loc.country) CONTAINS search_loc
                    )
                )
                AND
                ANY(edu IN education WHERE 
                    ANY(search_edu IN $education_lower WHERE 
                        toLower(edu.institution) CONTAINS search_edu OR
                        toLower(edu.degree) CONTAINS search_edu
                    )
                )
                """
                )
            if "location" in search_params and search_params["location"] and "education" not in search_params:
                query_parts.append(
                    """
                WHERE ANY(loc IN locations WHERE 
                    ANY(search_loc IN $locations_lower WHERE 
                        toLower(loc.name) CONTAINS search_loc OR
                        toLower(loc.city) CONTAINS search_loc OR
                        toLower(loc.state) CONTAINS search_loc OR
                        toLower(loc.country) CONTAINS search_loc
                    )
                )
                """
                )

            # Apply education filter if specified
            if "education" in search_params and search_params["education"] and "location" not in search_params:
                query_parts.append(
                    """
                WHERE ANY(edu IN education WHERE 
                    ANY(search_edu IN $education_lower WHERE 
                        toLower(edu.institution) CONTAINS search_edu OR
                        toLower(edu.degree) CONTAINS search_edu
                    )
                )
                """
                )


        # Apply location filter if specified
        # if "location" in search_params and search_params["location"]:
        #     query_parts.append(
        #         """
        #     WHERE ANY(loc IN locations WHERE 
        #         ANY(search_loc IN $locations_lower WHERE 
        #             toLower(loc.name) CONTAINS search_loc OR
        #             toLower(loc.city) CONTAINS search_loc OR
        #             toLower(loc.state) CONTAINS search_loc OR
        #             toLower(loc.country) CONTAINS search_loc
        #         )
        #     )
        #     """
        #     )

        # # Apply education filter if specified
        # if "education" in search_params and search_params["education"]:
        #     query_parts.append(
        #         """
        #     WHERE ANY(edu IN education WHERE 
        #         ANY(search_edu IN $education_lower WHERE 
        #             toLower(edu.institution) CONTAINS search_edu OR
        #             toLower(edu.degree) CONTAINS search_edu
        #         )
        #     )
        #     """
        #     )

        # Return results
        query_parts.append(
            """
        RETURN c as candidate, 
               all_skills as total_skills,
               matched_skills,
               current_designation,
               matched_roles,
               locations,
               education,
               companies
        """
        )
        

        return "\n".join(query_parts)
    
    # Prepare Query Parameters
    def _prepare_query_params(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare query parameters with lowercase versions for case-insensitive search"""
        params = {}

        if "email" in search_params and search_params["email"]:
            # Handle both string and list for email
            if isinstance(search_params["email"], list):
                params["email"] = (
                    search_params["email"][0] if search_params["email"] else None
                )
            else:
                params["email"] = search_params["email"]

        if "phone" in search_params and search_params["phone"]:
            # Handle both string and list for phone
            if isinstance(search_params["phone"], list):
                
                params["phone"] = " ".join(search_params["phone"]).strip()
            else:
                params["phone"] = search_params["phone"].strip()
                
            print(params["phone"])

        if "name" in search_params and search_params["name"]:
            # Handle both string and list for name
            if isinstance(search_params["name"], list):
                
                params["name"] = " ".join(search_params["name"]).strip()
            else:
                
                params["name"] = search_params["name"].strip()
            

        if "skills" in search_params and search_params["skills"]:
            # Ensure skills is a list
            if isinstance(search_params["skills"], str):
                params["skills_lower"] = [search_params["skills"].lower()]
            else:
                params["skills_lower"] = [
                    skill.lower() for skill in search_params["skills"]
                ]

        if "role" in search_params and search_params["role"]:
            # Ensure role is a list
            if isinstance(search_params["role"], str):
                params["roles_lower"] = [search_params["role"].lower()]
            else:
                params["roles_lower"] = [role.lower() for role in search_params["role"]]

        if "location" in search_params and search_params["location"]:
            # Ensure location is a list
            if isinstance(search_params["location"], str):
                params["locations_lower"] = [search_params["location"].lower()]
            else:
                params["locations_lower"] = [
                    loc.lower() for loc in search_params["location"]
                ]

        if "education" in search_params and search_params["education"]:
            # Ensure education is a list
            if isinstance(search_params["education"], str):
                params["education_lower"] = [search_params["education"].lower()]
            else:
                params["education_lower"] = [
                    edu.lower() for edu in search_params["education"]
                ]

        return params
    
    # Calculate Match Scores 
    def _calculate_match_scores(
        self,
        record: Any,
        search_params: Dict[str, Any],
        search_embedding: Optional[List[float]],
        candidate_embedding: Optional[List[float]],
    ) -> Dict[str, float]:
        """Calculate various match scores for a candidate"""
        scores = {
            "skill_score": 0.0,
            "role_score": 0.0,
            "location_score": 0.0,
            "education_score": 0.0,
            "similarity_score": 0.0,
            "total_score": 0.0,
        }
        name_only_search = "name" in search_params and not any(
            k in search_params and search_params[k]
            for k in ["skills", "role", "location", "education"]
        )

        if name_only_search:
            scores["total_score"] = 1.0
            return scores

        # Calculate skill match score
        if "skills" in search_params and search_params["skills"]:
            matched_skills = record.get("matched_skills", [])
            requested_skills = search_params["skills"]
            if requested_skills:
                
                scores["skill_score"] = len(matched_skills) / len(requested_skills)

        # Calculate role match score
        if "role" in search_params and search_params["role"]:
            matched_roles = record.get("matched_roles", [])
            requested_roles = search_params["role"]
            if requested_roles:
                
                scores["role_score"] = len(matched_roles) / len(requested_roles)

        # Calculate location match score
        if "location" in search_params and search_params["location"]:
            locations = record.get("locations", [])
            if locations and search_params["location"]:
                location_matches = 0
                for loc in locations:
                    for search_loc in search_params["location"]:
                        if (
                            search_loc.lower() in str(loc.get("name", "")).lower()
                            or search_loc.lower() in str(loc.get("city", "")).lower()
                            or search_loc.lower() in str(loc.get("state", "")).lower()
                            or search_loc.lower() in str(loc.get("country", "")).lower()
                        ):
                            location_matches += 1
                            break
                scores["location_score"] = min(
                    location_matches / len(search_params["location"]), 1.0
                )

        # Calculate education match score
        if "education" in search_params and search_params["education"]:
            education = record.get("education", [])
            if education and search_params["education"]:
                edu_matches = 0
                for edu in education:
                    for search_edu in search_params["education"]:
                        if (
                            search_edu.lower()
                            in str(edu.get("institution", "")).lower()
                            or search_edu.lower() in str(edu.get("degree", "")).lower()
                        ):
                            edu_matches += 1
                            break
                scores["education_score"] = min(
                    edu_matches / len(search_params["education"]), 1.0
                )

        # Calculate embedding similarity score
        if search_embedding and candidate_embedding:
            scores["similarity_score"] = self.calculate_similarity(
                search_embedding, candidate_embedding
            )

        # Calculate total score (weighted average)
        weights = {
            "skill_score": 0.3,
            "role_score": 0.25,
            "location_score": 0.15,
            "education_score": 0.1,
            "similarity_score": 0.2,
        }

        # Adjust weights based on what's being searched
        active_criteria = sum(1 for k in weights.keys() if scores[k] > 0)
        if active_criteria > 0:
            # Normalize weights for active criteria
            active_weight_sum = sum(
                weights[k]
                for k in weights.keys()
                if scores[k] > 0 or k == "similarity_score"
            )

            for key in weights:
                if scores[key] > 0 or key == "similarity_score":
                    adjusted_weight = weights[key] / active_weight_sum
                    scores["total_score"] += scores[key] * adjusted_weight

        return scores

# Search Resume (Async)
async def search_resume(search_query,from_experience,to_experience,similarity_threshold):
    # Initialize search engine
    search_engine = CandidateSearchEngine(
        uri=NEO4jURI, user=NEO4jUSER, password=NEO4jPASSWORD
    )

    try:


        print("Searching for candidates:")
        # Search Candidates from the Neo4J DB
        results = await search_engine.search_candidates(
            search_params=search_query,
            from_experience=from_experience,
            to_experience=to_experience,
            top_k=20,
            similarity_threshold=similarity_threshold,
        )
        # print(results)
        # print(f"Found {len(results)} matching candidates:\n")
        # for i, candidate in enumerate(results, 1):
        #     print(f"{i}. {candidate['name']}")
        #     print(f"   Email: {candidate['email']}")
        #     print(f"   Phone Number: {candidate['phone']}")
        #     print(f"   Experience: {candidate['years_experience']} years")
        #     print(f"   Current Role: {candidate['current_designation']}")
        #     print(f"   Matched Skills: {', '.join(candidate['matched_skills'])}")
        #     print(f"   Total Score: {candidate['total_score']:.2f}")
        #     print(f"   - Skill Score: {candidate['skill_score']:.2f}")
        #     print(f"   - Role Score: {candidate['role_score']:.2f}")
        #     print(f"   - Location Score: {candidate['location_score']:.2f}")
        #     print(f"   - Similarity Score: {candidate['similarity_score']:.2f}")
        return results

    except Exception as e:
        print(f"Error during search: {e}")

    finally:
        search_engine.close()



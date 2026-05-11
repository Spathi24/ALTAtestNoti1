/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;

/**
 * -----------------------------------------------------------------------------
 * Value objects / reference data (compile-safe Java types)
 * -----------------------------------------------------------------------------
 * ISO-8601 timestamp wrapper (avoids DateTime missing-type issues in Java).
 */
// line 77 "../../model-v0.1.ump"
public class DateTime
{

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //DateTime Attributes
  private String value;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public DateTime(String aValue)
  {
    value = aValue;
  }

  //------------------------
  // INTERFACE
  //------------------------

  public String getValue()
  {
    return value;
  }

  public void delete()
  {}


  public String toString()
  {
    return super.toString() + "["+
            "value" + ":" + getValue()+ "]";
  }
}
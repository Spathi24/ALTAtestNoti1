/*PLEASE DO NOT EDIT THIS CODE*/
/*This code was generated using the UMPLE 1.37.0.8623.1cd95c4b0 modeling language!*/

package project_db.v01;

/**
 * Exact decimal wrapper (avoid floating-point for money).
 */
// line 82 "../../model-v0.1.ump"
public class Decimal
{

  //------------------------
  // MEMBER VARIABLES
  //------------------------

  //Decimal Attributes
  private String value;

  //------------------------
  // CONSTRUCTOR
  //------------------------

  public Decimal(String aValue)
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